from __future__ import annotations
"""Smart Crawler (v2)
====================
CLI helper that looks for ``outputs/discovered_pages_final.json`` (the list that
comes **after** the human has tick‑boxed their final URL selection). If the file
is missing it prints a helpful hint and exits. Otherwise it:

1. Shows the URL list back to the user.
2. Asks **Proceed with crawl? (y/n)**.
3. If *y* – crawls each URL using *crawl4ai* for extraction, summarises via an
   LLM **only if** ``OPENAI_API_KEY`` (or Anthropic / Gemini / Groq) is present.
4. Writes one JSON file per page under ``outputs/`` using the ``PageContent``
   schema (see ``schema.py``).
5. Prints a neat completion report listing the files created.

Run:
```bash
python smart_crawler/smart_crawler.py
```
No arguments required.
"""

from pathlib import Path
import json
import os
import re
import sys
from typing import List, Sequence

from dotenv import load_dotenv
from rich import print  # pretty console output

# ---------------------------------------------------------------------------
# 1️⃣  Environment / constants
# ---------------------------------------------------------------------------

load_dotenv()
BASE_DIR = Path.cwd()
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
FINAL_URL_FILE = OUTPUT_DIR / "discovered_pages_final.json"

# Optional LLM keys (we'll pick whichever is present)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------------------------------------------------------------------------
# 2️⃣  Schema import (Pydantic) – ensures we serialise correctly
# ---------------------------------------------------------------------------

from .schema import PageContent, Section  # noqa: E402  (local import after Path setup)

# ---------------------------------------------------------------------------
# 3️⃣  Utility helpers
# ---------------------------------------------------------------------------


def slugify(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", url.strip("/ ").lower()).strip("-") or "root"


# ---------------------------------------------------------------------------
# 4️⃣  Extraction via crawl4ai  ----------------------------------------------
# ---------------------------------------------------------------------------

from crawl4ai.extractors import BasicExtractor  # type: ignore
from crawl4ai.core import SimpleCrawler       # type: ignore


class SectioningExtractor(BasicExtractor):
    """Extend BasicExtractor → split HTML into heading‑based sections."""

    def parse(self, html: str, url: str):  # type: ignore[override]
        soup = self.soup(html)
        # strip noise
        for tag in soup(["nav", "footer", "script", "style", "noscript", "svg"]):
            tag.decompose()

        current: Section | None = None
        sections: list[Section] = []

        def flush():
            nonlocal current
            if current and (current.body or current.images):
                sections.append(current)
            current = None

        for el in soup.body.descendants:  # type: ignore[attr-defined]
            if el.name in {"h1", "h2", "h3"}:
                flush()
                heading = el.get_text(" ", strip=True)
                current = Section(id=slugify(heading), heading=heading)
            elif el.name in {"p", "li"}:
                text = el.get_text(" ", strip=True)
                if text:
                    if current is None:
                        current = Section(id="intro")
                    current.body += text + "\n"
            elif el.name == "img" and (src := el.get("src")):
                if current is None:
                    current = Section(id="intro")
                current.images.append({"src": src, "alt": el.get("alt", "")})

        flush()
        return {"sections": sections}


# crawler instance is cheap; create global
CRAWLER = SimpleCrawler(extractor=SectioningExtractor())


# ---------------------------------------------------------------------------
# 5️⃣  Optional LLM summariser (auto‑detect provider) ------------------------
# ---------------------------------------------------------------------------


def _noop(text: str) -> str:  # fallback
    return text


try:
    if OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.2)
    elif ANTHROPIC_API_KEY:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model="claude-3-sonnet-20240229", api_key=ANTHROPIC_API_KEY, temperature=0.2)
    elif GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(model="gemini-pro", api_key=GOOGLE_API_KEY, temperature=0.2)
    elif GROQ_API_KEY:
        from langchain_groq import ChatGroq

        llm = ChatGroq(model="llama3-8b-8192", api_key=GROQ_API_KEY, temperature=0.2)
    else:
        llm = None
except Exception as e:  # pragma: no cover
    print(f"[yellow]  LLM init failed ({e}), falling back to raw text summaries.[/yellow]")
    llm = None


if llm:

    def summarise(text: str) -> str:  # noqa: D401  (simple verb ok)
        prompt = (
            "You are a senior copy‑writer. Rewrite the following website copy "
            "concisely in **markdown**, keep voice, keep CTAs, keep lists.\n\n" + text
        )
        try:
            return llm.invoke(prompt).content.strip()
        except Exception as exc:  # pragma: no cover
            print(f"[red]LLM error[/red]: {exc}. Using raw text.")
            return text
else:
    summarise = _noop  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 6️⃣  Core crawl pipeline ---------------------------------------------------
# ---------------------------------------------------------------------------


def crawl_url(url: str) -> Path | None:
    try:
        data = CRAWLER.extract(url)
    except Exception as exc:
        print(f"[red]✖[/red] {url}  ({exc})")
        return None

    # Convert to our Pydantic schema & summarise
    sections: list[Section] = []
    for r in data["sections"]:
        sec = Section(**r)
        sec.body = summarise(sec.body)
        sections.append(sec)

    page_name = slugify(url.replace("http://", "").replace("https://", ""))
    page_name = page_name.split("-")[0] or "homepage"

    page = PageContent(page=page_name, url=url, sections=sections)
    out_file = OUTPUT_DIR / f"{page_name}.json"
    out_file.write_text(page.to_json())
    print(f"[green]✔[/green] saved {out_file.relative_to(BASE_DIR)}")
    return out_file


# ---------------------------------------------------------------------------
# 7️⃣  CLI entry -------------------------------------------------------------
# ---------------------------------------------------------------------------


def load_final_urls() -> Sequence[str]:
    if not FINAL_URL_FILE.exists():
        print(
            "[red]❌  Missing[/red] outputs/discovered_pages_final.json. "
            "Run discovery & select pages first."
        )
        sys.exit(1)

    data = json.loads(FINAL_URL_FILE.read_text())
    return [d["url"] if isinstance(d, dict) else d for d in data]


def main() -> None:  # pragma: no cover
    urls = load_final_urls()

    print("\n[b]Target URLs[/b] (from discovered_pages_final.json):")
    for u in urls:
        print(f" • {u}")

    proceed = input("\nProceed with crawl? (y/n): ").strip().lower()
    if proceed != "y":
        print("Aborted by user.")
        return

    print("\n[cyan]Starting crawl…[/cyan]\n")
    created: list[Path] = []
    for u in urls:
        out = crawl_url(u)
        if out:
            created.append(out)

    if created:
        print("\n[bold green]✅  Crawl complete[/bold green]")
        for f in created:
            print(f"  • {f.relative_to(BASE_DIR)}")
    else:
        print("\n[red]No pages saved.[/red]")


if __name__ == "__main__":
    main()
