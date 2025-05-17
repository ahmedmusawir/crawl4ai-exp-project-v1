from __future__ import annotations
"""Smart Crawler (v2)
====================
CLI helper that looks for ``outputs/discovered_pages_final.json`` (the list that
comes **after** the human has tick‑boxed their final URL selection). If the file
is missing it prints a helpful hint and exits. Otherwise it:

1. Shows the URL list back to the user.
2. Asks **Proceed with crawl? (y/n)**.
3. If *y* – crawls each URL using *crawl4ai* for extraction, summarises via an
   LLM **only if** an API key (OpenAI / Anthropic / Gemini / Groq) is present.
4. Writes one JSON file per page under ``outputs/`` using the ``PageContent``
   schema (see ``schema.py``).
5. Prints a neat completion report listing the files created.

Run:
```bash
python smart_crawler/smart_crawler.py        # or
python -m smart_crawler.smart_crawler
```
"""

from pathlib import Path
import asyncio
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

# Optional LLM keys (auto‑detect provider)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------------------------------------------------------------------------
# 2️⃣  Schema import (Pydantic) – ensures we serialise correctly
# ---------------------------------------------------------------------------

try:
    from .schema import PageContent, Section  # when executed as a module
except ImportError:
    from smart_crawler.schema import PageContent, Section  # direct path exec

# ---------------------------------------------------------------------------
# 3️⃣  Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip("/ ").lower()).strip("-") or "root"

# ---------------------------------------------------------------------------
# 4️⃣  Extraction via Crawl4AI ≥ 0.6
# ---------------------------------------------------------------------------

from crawl4ai import AsyncWebCrawler  # type: ignore

CRAWLER = AsyncWebCrawler()  # single shared instance manages its own context

# ---------------------------------------------------------------------------
# 5️⃣  Optional LLM summariser (LangChain multi‑provider)
# ---------------------------------------------------------------------------

def _noop(text: str) -> str:
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
except Exception as e:
    print(f"[yellow]LLM init failed ({e}); falling back to raw text.[/yellow]")
    llm = None

if llm:
    def summarise(text: str) -> str:
        prompt = (
            "You are a senior copy‑writer. Rewrite the following website copy "
            "concisely in **markdown**, keep voice, calls‑to‑action and lists.\n\n" + text
        )
        try:
            return llm.invoke(prompt).content.strip()
        except Exception as exc:
            print(f"[red]LLM error[/red]: {exc}. Using raw text.")
            return text
else:
    summarise = _noop  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# 6️⃣  Core crawl pipeline
# ---------------------------------------------------------------------------

async def fetch_markdown(url: str) -> str:
    """Return cleaned Markdown from Crawl4AI."""
    result = await CRAWLER.arun(url)
    return getattr(result.markdown, "fit_markdown", result.markdown).strip()


aSYNC_HEADING = re.compile(r"^#{1,3}\s+")

async def crawl_url(url: str) -> Path | None:
    try:
        markdown = await fetch_markdown(url)
    except Exception as exc:
        print(f"[red]✖[/red] {url}  ({exc})")
        return None

    sections: List[Section] = []
    current = Section(id="intro")
    for line in markdown.splitlines():
        if aSYNC_HEADING.match(line):
            if current.body:
                sections.append(current)
            heading = line.lstrip("# ").strip()
            current = Section(id=slugify(heading), heading=heading)
        else:
            current.body += line + "\n"

    if current.body or current.images:
        sections.append(current)

    for sec in sections:
        sec.body = summarise(sec.body)

    page_name = slugify(url.replace("http://", "").replace("https://", ""))
    page_name = page_name.split("-")[0] or "homepage"
    page = PageContent(page=page_name, url=url, sections=sections)

    out_path = OUTPUT_DIR / f"{page_name}.json"
    out_path.write_text(page.to_json())
    print(f"[green]✔[/green] saved {out_path.relative_to(BASE_DIR)}")
    return out_path

# ---------------------------------------------------------------------------
# 7️⃣  CLI helpers
# ---------------------------------------------------------------------------

def load_final_urls() -> Sequence[str]:
    if not FINAL_URL_FILE.exists():
        print("[red]❌  Missing[/red] outputs/discovered_pages_final.json. Run discovery first.")
        sys.exit(1)

    data = json.loads(FINAL_URL_FILE.read_text())
    return [d["url"] if isinstance(d, dict) else d for d in data]


def main() -> None:  # pragma: no cover
    urls = list(load_final_urls())

    print("\n[b]Target URLs[/b] (from discovered_pages_final.json):")
    for u in urls:
        print(f" • {u}")

    if input("\nProceed with crawl? (y/n): ").strip().lower() != "y":
        print("Aborted by user.")
        return

    print("\n[cyan]Starting crawl…[/cyan]\n")

    async def crawl_all(targets: list[str]):
        return await asyncio.gather(*(crawl_url(u) for u in targets))

    created = [p for p in asyncio.run(crawl_all(urls)) if p]

    if created:
        print("\n[bold green]✅  Crawl complete[/bold green]")
        for f in created:
            print(f"  • {f.relative_to(BASE_DIR)}")
    else:
        print("\n[red]No pages saved.[/red]")


if __name__ == "__main__":
    main()
