from __future__ import annotations
import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv
from rich import print

# -- import our Pydantic models (PageContent, Section) --
from smart_crawler.schema import PageContent, Section

# ---------------------------------------------------------------------------
# 1️⃣  Paths
# ---------------------------------------------------------------------------
load_dotenv()
BASE_DIR = Path.cwd()
INPUT_DIR = BASE_DIR / "outputs" / "pages"
OUTPUT_DIR = BASE_DIR / "outputs" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 2️⃣  Optional LLM summariser (multi‑provider)
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
    print(f"[yellow]LLM init failed ({e}); falling back to raw text[/yellow]")
    llm = None

if llm:
    def summarise(text: str) -> str:
        prompt = (
            "You are a senior technical writer. Rewrite the following section as a concise markdown summary, preserving key details, CTAs, and structure:\n\n" + text
        )
        try:
            return llm.invoke(prompt).content.strip()
        except Exception as exc:
            print(f"[red]LLM error[/red]: {exc}. Using raw text.")
            return text
else:
    summarise = _noop  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# 3️⃣  Helpers
# ---------------------------------------------------------------------------
def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-") or "root"

# ---------------------------------------------------------------------------
# 4️⃣  Section splitting into Pydantic Sections
# ---------------------------------------------------------------------------
def section_splitter(markdown: str) -> list[Section]:
    lines = markdown.splitlines()
    sections: list[Section] = []
    # initialize with an intro section
    current = Section(id="intro", heading=None, body="", images=[])

    for line in lines:
        if line.startswith("#") and re.match(r"^#{1,3}\s+", line):
            # flush previous
            if current.body.strip() or current.images:
                sections.append(current)
            heading = line.lstrip("# ").strip()
            current = Section(id=slugify(heading), heading=heading, body="", images=[])
        else:
            current.body += line + "\n"

    # final flush
    if current.body.strip() or current.images:
        sections.append(current)

    # optionally summarise each section
    for sec in sections:
        sec.body = summarise(sec.body)

    return sections

# ---------------------------------------------------------------------------
# 5️⃣  Process a single markdown file → JSON
# ---------------------------------------------------------------------------
def process_file(md_path: Path) -> Path | None:
    print(f"Processing: [cyan]{md_path.name}[/cyan]")
    content = md_path.read_text(encoding="utf-8").strip()
    if not content:
        print(f"[yellow]⚠️ Empty file:[/yellow] {md_path.name}")
        return None

    # derive URL from filename
    url_stub = md_path.stem.replace("-", ".")
    url = f"https://{url_stub}"

    # split into sections
    sections = section_splitter(content)
    if not sections:
        print(f"[yellow]⚠️ No sections parsed for:[/yellow] {md_path.name}")
        return None

    # build PageContent
    page = PageContent(page=md_path.stem, url=url, sections=sections)
    out_path = OUTPUT_DIR / f"{md_path.stem}.json"
    try:
        # Pydantic v2 safe dump
        out_path.write_text(page.model_dump_json(indent=2), encoding="utf-8")
        print(f"[green]✔ Saved:[/green] {out_path.relative_to(BASE_DIR)}")
        return out_path
    except Exception as e:
        print(f"[red]❌ Failed to write {out_path.name}:[/red] {e}")
        return None

# ---------------------------------------------------------------------------
# 6️⃣  CLI entry
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
        print("Successfully created JSON:")
        for p in created:
            print(f" • {p.relative_to(BASE_DIR)}")
    else:
        print("[yellow]No JSON files created.[/yellow]")

if __name__ == "__main__":
    main()
