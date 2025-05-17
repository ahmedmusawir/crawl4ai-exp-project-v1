from __future__ import annotations
"""
Markdown to JSON Processor (LangChain Optional)
=================================================
✓ Loads `.md` files from `outputs/pages/`
✓ Converts to structured `.json` using section splitting
✓ Summarises via LLM if API key is found
✓ Writes to `outputs/json/` as JSON

Run:
```bash
python -m smart_crawler.data_processing
```
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Sequence
from dotenv import load_dotenv
from rich import print

from smart_crawler.schema import PageContent, Section

# ---------------------------------------------------------------------------
# 1️⃣ Constants and paths
# ---------------------------------------------------------------------------

load_dotenv()
BASE_DIR = Path.cwd()
INPUT_DIR = BASE_DIR / "outputs/pages"
OUTPUT_DIR = BASE_DIR / "outputs/json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 2️⃣ Optional LLM summariser (LangChain multi‑provider)
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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
            "You are a senior content strategist. For each section of the markdown content below, "
            "generate a concise, structured summary in markdown. Preserve meaningful structure, CTAs, and clarity.\n\n" + text
        )
        try:
            return llm.invoke(prompt).content.strip()
        except Exception as exc:
            print(f"[red]LLM error[/red]: {exc}. Using raw text.")
            return text
else:
    summarise = _noop  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# 3️⃣ Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-") or "root"

def section_splitter(markdown: str) -> list[Section]:
    lines = markdown.splitlines()
    sections: list[Section] = []
    current = Section(id="intro", body="")

    for line in lines:
        if line.startswith("#") and len(line.strip().split()) > 1:
            if current.body:
                sections.append(current)
            heading = line.lstrip("# ").strip()
            current = Section(id=slugify(heading), heading=heading, body="")
        else:
            current.body += line + "\n"

    if current.body:
        sections.append(current)

    for sec in sections:
        sec.body = summarise(sec.body)

    return sections

# ---------------------------------------------------------------------------
# 4️⃣ Processor function
# ---------------------------------------------------------------------------

def process_file(md_path: Path) -> Path | None:
    print(f"Processing: [cyan]{md_path.name}[/cyan]")

    try:
        content = md_path.read_text(encoding="utf-8").strip()
        if not content:
            print(f"[yellow]⚠️ Empty file:[/yellow] {md_path.name}")
            return None

        url_stub = md_path.stem.replace("-", ".")
        page = PageContent(
            page=md_path.stem,
            url=f"https://{url_stub}",
            sections=section_splitter(content)
        )

        out_path = OUTPUT_DIR / f"{md_path.stem}.json"
        out_path.write_text(page.to_json(indent=2), encoding="utf-8")
        print(f"[green]✔ Saved:[/green] {out_path.relative_to(BASE_DIR)}")
        return out_path

    except Exception as e:
        print(f"[red]❌ Failed:[/red] {md_path.name} — {e}")
        return None

# ---------------------------------------------------------------------------
# 5️⃣ CLI entry
# ---------------------------------------------------------------------------

def main():
    files = sorted(INPUT_DIR.glob("*.md"))
    if not files:
        print("[red]❌ No markdown files found in 'outputs/pages'.[/red]")
        sys.exit(1)

    print("\n[bold]These markdown files will be processed into JSON:[/bold]")
    for f in files:
        print(f" • {f.name}")

    if input("\nProceed with processing? (y/n): ").strip().lower() != "y":
        print("Aborted.")
        return

    print("\n[cyan]Processing begins…[/cyan]\n")
    created = [p for p in (process_file(f) for f in files) if p]

    print("\n[bold green]✅ Processing complete[/bold green]")
    if created:
        for p in created:
            print(f" • {p.relative_to(BASE_DIR)}")
    else:
        print("[yellow]No JSON files created.[/yellow]")

if __name__ == "__main__":
    main()
