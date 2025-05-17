from __future__ import annotations

"""Smart Crawler
-----------------
Crawls a list of URLs, extracts per‑section content, optionally summarizes via
OpenAI, and writes JSON files conforming to `schema.PageContent`.

Usage
~~~~~
```bash
python smart_crawler/smart_crawler.py --urls outputs/discovered_pages.json
```

Dependencies
~~~~~~~~~~~~
- requests
- beautifulsoup4
- pydantic (imported via schema)
- python-dotenv (optional, if using .env)

Environment
~~~~~~~~~~~
Load `.env` automatically.  If `OPENAI_API_KEY` is present the crawler will call
OpenAI GPT‑4o for **tone‑preserving summarisation**.  Otherwise it dumps raw
HTML text blocks.
"""

from pathlib import Path
import argparse
import json
import os
import re
import textwrap
from typing import List

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from dotenv import load_dotenv

from .schema import PageContent, Section

# ---------------------------------------------------------------------------
# Config & Helpers
# ---------------------------------------------------------------------------

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Section Extraction Logic
# ---------------------------------------------------------------------------

def slugify(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", url.strip("/ ").lower()).strip("-") or "root"


def fetch_html(url: str) -> str:
    res = requests.get(url, headers=_HEADERS, timeout=15)
    res.raise_for_status()
    return res.text


def extract_sections_from_html(html: str) -> List[Section]:
    soup = BeautifulSoup(html, "html.parser")

    # Remove nav, footer, script, style, etc. so they don't pollute content
    for tag in soup(["nav", "footer", "script", "style", "noscript", "svg"]):
        tag.decompose()

    sections: List[Section] = []
    buffer_lines: List[str] = []
    current_id = "intro"
    heading_text: str | None = None
    image_urls: List[str] = []

    def flush():
        nonlocal buffer_lines, heading_text, image_urls, current_id
        text = "\n".join(buffer_lines).strip()
        if text or image_urls:
            sections.append(
                Section(
                    id=current_id,
                    heading=heading_text,
                    body=text,
                    images=[{"src": u, "alt": ""} for u in image_urls],
                )
            )
        # reset buffers
        buffer_lines = []
        heading_text = None
        image_urls = []

    for node in soup.body.descendants:  # type: ignore[attr-defined]
        if isinstance(node, Tag):
            if node.name in {"h1", "h2", "h3"}:
                flush()
                heading_text = node.get_text(" ", strip=True)
                current_id = slugify(heading_text)
            elif node.name == "img" and (src := node.get("src")):
                image_urls.append(src)
            elif node.name in {"p", "li"}:
                text = node.get_text(" ", strip=True)
                if text:
                    buffer_lines.append(text)
        elif isinstance(node, NavigableString):
            pass  # ignore loose strings (handled by parents)

    flush()
    return sections


# ---------------------------------------------------------------------------
# OpenAI Summarisation (optional)
# ---------------------------------------------------------------------------

if OPENAI_API_KEY:
    import openai

    openai.api_key = OPENAI_API_KEY


    def summarise(text: str, max_tokens: int = 400) -> str:
        """Summarise while preserving tone and key details."""

        system = (
            "You are a senior copywriter. Preserve voice and all bullet points. "
            "Make the text concise but complete. Don't remove CTAs or numbers.""
        )
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",  # cost‑effective, adjust if needed
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": textwrap.dedent(
                        f"""
                        ORIGINAL TEXT:\n\n{text}\n\n---\nProvide a cleaned, markdown‑friendly version keeping full meaning.
                        """
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
else:

    def summarise(text: str, *_, **__) -> str:  # type: ignore[override]
        return text  # no‑op if no API key


# ---------------------------------------------------------------------------
# Main Crawler Logic
# ---------------------------------------------------------------------------


def process_url(url: str) -> None:
    print(f"[crawl] {url}")
    html = fetch_html(url)
    sections = extract_sections_from_html(html)

    # Optional LLM pass per section
    for sec in sections:
        sec.body = summarise(sec.body)

    slug = slugify(url.replace("http://", "").replace("https://", ""))
    page_name = slug.split("-")[0] if slug else "homepage"

    page = PageContent(page=page_name, url=url, sections=sections)

    outfile = OUTPUT_DIR / f"{page_name}.json"
    outfile.write_text(page.to_json())
    print(f"  → saved {outfile.relative_to(Path.cwd())}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Crawler – structured AI scraping")
    parser.add_argument("--urls", required=True, help="Path to JSON file with list[{'url': ...}] or list[str]")
    args = parser.parse_args()

    url_file = Path(args.urls)
    if not url_file.exists():
        parser.error(f"file not found: {url_file}")

    data = json.loads(url_file.read_text())
    urls: List[str] = [d["url"] if isinstance(d, dict) else d for d in data]

    for url in urls:
        try:
            process_url(url)
        except Exception as exc:
            print(f"[error] {url}: {exc}")


if __name__ == "__main__":
    main()
