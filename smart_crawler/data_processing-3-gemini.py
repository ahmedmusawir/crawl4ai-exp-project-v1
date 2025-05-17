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
import json # json module is imported but not directly used; Pydantic handles JSON conversion
import re
from pathlib import Path
# from typing import Sequence # Sequence is imported but not used in type hints
from dotenv import load_dotenv
from rich import print

# Assuming smart_crawler.schema contains Pydantic models
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

llm = None # Initialize llm to None

def _noop(text: str) -> str:
    """Fallback function if no LLM is available or if summarization fails."""
    return text

try:
    if OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.2)
        print("[green]Using OpenAI for summarization.[/green]")
    elif ANTHROPIC_API_KEY:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-3-sonnet-20240229", api_key=ANTHROPIC_API_KEY, temperature=0.2)
        print("[green]Using Anthropic for summarization.[/green]")
    elif GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(model="gemini-pro", api_key=GOOGLE_API_KEY, temperature=0.2) # Ensure GOOGLE_API_KEY is correctly named if it's GOOGLE_APPLICATION_CREDENTIALS for some setups
        print("[green]Using Google GenAI for summarization.[/green]")
    elif GROQ_API_KEY:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model="llama3-8b-8192", api_key=GROQ_API_KEY, temperature=0.2)
        print("[green]Using Groq for summarization.[/green]")
    else:
        print("[yellow]No LLM API key found. Summarization will be skipped (raw text will be used).[/yellow]")
        # llm remains None, _noop will be used
except ImportError as ie:
    print(f"[yellow]LLM library import failed ({ie}); a required library might be missing. Falling back to raw text.[/yellow]")
    llm = None # Ensure llm is None if import fails
except Exception as e:
    print(f"[yellow]LLM init failed ({e}); falling back to raw text.[/yellow]")
    llm = None # Ensure llm is None on other exceptions

# Define summarise function based on whether an LLM was successfully initialized
if llm:
    def summarise(text: str) -> str:
        """Summarises text using the configured LLM."""
        if not text.strip(): # Don't send empty strings to LLM
            return ""
        prompt = (
            "You are a senior content strategist. For the markdown content section below, "
            "generate a concise, structured summary in markdown. Preserve meaningful structure, CTAs, and clarity. "
            "If the content is very short or already a summary, you can return it as is or with minimal changes.\n\n"
            "Content to summarise:\n---\n"
            f"{text}\n---\n"
            "Summary:"
        )
        try:
            response = llm.invoke(prompt)
            # Assuming response has a 'content' attribute for LangChain v0.1.x+
            summary_content = getattr(response, 'content', str(response))
            return summary_content.strip()
        except Exception as exc:
            print(f"[red]LLM summarization error[/red]: {exc}. Using raw text for this section.")
            return text # Fallback to original text for this section on error
else:
    summarise = _noop # type: ignore[assignment]
    if not (OPENAI_API_KEY or ANTHROPIC_API_KEY or GOOGLE_API_KEY or GROQ_API_KEY):
        # This message was already printed if no keys were found.
        # Only print if LLM initialization failed for other reasons after a key was present.
        if any([OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, GROQ_API_KEY]):
             print("[yellow]Summarization will use raw text due to LLM initialization failure.[/yellow]")


# ---------------------------------------------------------------------------
# 3️⃣ Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Converts text to a URL-friendly slug."""
    # Remove any leading/trailing non-alphanumeric characters that might arise after stripping '#'
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text)
    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r"[^a-z0-9\s-]", "", text.strip().lower())
    # Replace whitespace and multiple hyphens with a single hyphen
    text = re.sub(r"\s+|-+", "-", text)
    return text.strip("-") or "root" # Ensure not empty, default to "root"

def section_splitter(markdown: str, filename_for_context: str) -> list[Section]:
    """Splits markdown content into sections based on headings."""
    lines = markdown.splitlines()
    sections: list[Section] = []
    current_section_body_lines: list[str] = []
    current_heading: str | None = None
    # Default for content before the first heading
    current_id: str = "intro"

    for line_number, line in enumerate(lines):
        stripped_line = line.strip()
        # Detects lines starting with #, ##, ### etc. followed by a space and text
        if stripped_line.startswith("#") and " " in stripped_line and stripped_line.split(" ", 1)[1].strip():
            # If there's content in the current section (either intro or a previous headed section), save it
            if current_heading is not None or current_section_body_lines: # Save previous section
                body_content = "\n".join(current_section_body_lines).strip()
                sections.append(Section(
                    id=current_id,
                    heading=current_heading if current_heading is not None else "Introduction", # Provide a default heading for the intro section
                    body=summarise(body_content) # Summarise the collected body
                ))
                current_section_body_lines = [] # Reset for the new section

            # Start a new section
            heading_level = stripped_line.count("#", 0, stripped_line.find(" "))
            current_heading = stripped_line.lstrip("# ").strip()
            current_id = slugify(current_heading)
            if not current_id: # If slugify returns empty (e.g. heading was only symbols)
                current_id = f"section-{len(sections) + 1}"
            # Add the heading line itself to the body of the new section if you want it repeated in the 'body'
            # current_section_body_lines.append(line) # Optional: include heading in body
        else:
            current_section_body_lines.append(line)

    # Add the last section after the loop
    if current_heading is not None or current_section_body_lines:
        body_content = "\n".join(current_section_body_lines).strip()
        # If the entire document has no headings, it's all "intro"
        if not sections and current_id == "intro" and not current_heading:
             current_heading = "Full Page Content" # Or derive from filename
        
        sections.append(Section(
            id=current_id,
            heading=current_heading if current_heading is not None else "Content", # Default if no heading was ever found
            body=summarise(body_content)
        ))
    
    if not sections and not markdown.strip():
        print(f"[yellow]No content or sections found in {filename_for_context} after splitting.[/yellow]")
    elif not sections and markdown.strip(): # Markdown has content but no headers were parsed
        print(f"[yellow]Markdown content present in {filename_for_context} but no headers found to split by. Treating as single section.[/yellow]")
        sections.append(Section(
            id="full-content",
            heading=f"Full Content of {filename_for_context}",
            body=summarise(markdown.strip())
        ))


    return sections

# ---------------------------------------------------------------------------
# 4️⃣ Processor function
# ---------------------------------------------------------------------------

def process_file(md_path: Path) -> Path | None:
    """Processes a single markdown file into a JSON file."""
    print(f"Processing: [cyan]{md_path.name}[/cyan]")

    try:
        content = md_path.read_text(encoding="utf-8").strip()
        if not content:
            print(f"[yellow]⚠️ Empty file (no content):[/yellow] {md_path.name}")
            return None

        # Construct URL from filename (example: "company-about-us.md" -> "https://company.about.us")
        # This logic might need adjustment based on actual filename patterns
        url_parts = md_path.stem.split('-')
        if len(url_parts) > 1 and url_parts[0] == 'com': # specific handling for "com-..."
            domain = url_parts[1] + ".com"
            path_parts = url_parts[2:]
        else: # generic
            domain_parts = [p for p in url_parts if '.' in p or p in ['com','org','net','io']] # crude domain detection
            if not domain_parts:
                domain = url_parts[0] + ".com" # fallback
                path_parts = url_parts[1:]
            else: # simplistic, assumes first part with '.' or common tld is part of domain
                domain = url_parts[0] # needs better logic
                path_parts = url_parts[1:]


        url_stub = ".".join(filter(None, [md_path.stem.replace("-", ".")])) # Basic attempt
        # A more robust URL construction might be needed depending on filename conventions
        # For example, if filenames are like "cyberizegroup-com-privacy-policy"
        # stem = "cyberizegroup-com-privacy-policy"
        # A better URL might be "https://cyberizegroup.com/privacy-policy"
        # Current: "https://cyberizegroup.com.privacy.policy"
        
        # Attempt to reconstruct a more sensible URL
        # Example: cyberizegroup-com-privacy-policy.md -> https://cyberizegroup.com/privacy-policy
        filename_stem = md_path.stem
        parts = filename_stem.split('-')
        site_url = "https://example.com" # Default
        if len(parts) > 2 and parts[1] == "com": # Assuming "company-com-page" structure
            site_url = f"https://{parts[0]}.{parts[1]}"
            if len(parts) > 2:
                site_url += "/" + "-".join(parts[2:])
        else: # Fallback for other structures, e.g. "page-name" -> "https://page-name.com" (less ideal)
            site_url = f"https://{filename_stem.replace('-', '.')}" # This was the original problematic one

        # Let's try a slightly improved heuristic for URL from filename like "cyberizegroup-com-our-partners"
        # Target: https://cyberizegroup.com/our-partners
        
        file_stem_parts = md_path.stem.split('-')
        final_url = f"https://{md_path.stem.replace('-', '.')}" # Default fallback

        if len(file_stem_parts) > 1:
            # Check if the second part is a common TLD indicator like 'com', 'org', 'net'
            # and the first part could be the domain name.
            # e.g., "cyberizegroup-com-..."
            potential_tld_index = -1
            common_tlds = ["com", "org", "net", "io", "co", "us", "uk", "de", "fr"] # Add more if needed
            
            # Try to find '-com-', '-org-', etc.
            for i, part in enumerate(file_stem_parts):
                if part in common_tlds and i > 0:
                    potential_tld_index = i
                    break
            
            if potential_tld_index != -1:
                domain_name = "-".join(file_stem_parts[:potential_tld_index])
                tld = file_stem_parts[potential_tld_index]
                path_segments = file_stem_parts[potential_tld_index+1:]
                
                base_url = f"https://{domain_name}.{tld}"
                if path_segments:
                    final_url = f"{base_url}/{'-'.join(path_segments)}"
                else:
                    final_url = base_url
            else:
                # If no common TLD indicator found in that pattern, use a simpler heuristic
                # e.g., "sitemap.xml" or "about-us"
                if '.' in md_path.stem: # like "sitemap.xml"
                    final_url = f"https://example.com/{md_path.stem}" # Needs a base domain
                else: # like "about-us"
                    final_url = f"https://example.com/{md_path.stem}" # Needs a base domain
                                                            # Or if you know the domain:
                                                            # final_url = f"https://yourknownsite.com/{md_path.stem}"


        page = PageContent(
            page=md_path.stem,
            url=final_url, # Use the reconstructed URL
            sections=section_splitter(content, md_path.name)
        )

        out_path = OUTPUT_DIR / f"{md_path.stem}.json"
        
        # --- THIS IS THE CRITICAL FIX ---
        # Use model_dump_json() for Pydantic V2 to get an indented JSON string
        json_output = page.model_dump_json(indent=2)
        # --- END OF CRITICAL FIX ---
        
        out_path.write_text(json_output, encoding="utf-8")
        print(f"[green]✔ Saved:[/green] {out_path.relative_to(BASE_DIR)}")
        return out_path

    except Exception as e:
        # Print the full traceback for unexpected errors to help debug
        import traceback
        print(f"[red]❌ Failed to process file:[/red] {md_path.name}")
        print(f"[red]Error type:[/red] {type(e).__name__}")
        print(f"[red]Error message:[/red] {e}")
        print("[red]Traceback:[/red]")
        traceback.print_exc() # This will print the full stack trace to stderr
        return None

# ---------------------------------------------------------------------------
# 5️⃣ CLI entry
# ---------------------------------------------------------------------------

def main():
    """Main function to orchestrate the processing of markdown files."""
    if not INPUT_DIR.exists() or not any(INPUT_DIR.glob("*.md")):
        print(f"[red]❌ No markdown files found in '{INPUT_DIR}'. Please ensure .md files are present.[/red]")
        if not INPUT_DIR.exists():
            print(f"[yellow]Input directory '{INPUT_DIR}' does not exist.[/yellow]")
        sys.exit(1)

    files = sorted(INPUT_DIR.glob("*.md"))

    print("\n[bold]These markdown files will be processed into JSON:[/bold]")
    for f_path in files:
        print(f" • {f_path.name}")

    try:
        proceed = input("\nProceed with processing? (y/n): ").strip().lower()
    except KeyboardInterrupt:
        print("\n[yellow]Processing aborted by user.[/yellow]")
        sys.exit(0)
        
    if proceed != "y":
        print("Processing aborted.")
        return

    print("\n[cyan]Processing begins…[/cyan]\n")
    created_count = 0
    processed_files_paths: list[Path] = []

    for f_path in files:
        result_path = process_file(f_path)
        if result_path:
            processed_files_paths.append(result_path)
            created_count +=1

    print(f"\n[bold green]✅ Processing complete. {created_count} JSON file(s) created.[/bold green]")
    if processed_files_paths:
        for p_path in processed_files_paths:
            try:
                print(f" • {p_path.relative_to(BASE_DIR)}")
            except ValueError: # Should not happen if BASE_DIR is a parent
                print(f" • {p_path}")
    elif created_count == 0 and files:
         print("[yellow]No JSON files were created. Check logs for errors.[/yellow]")


if __name__ == "__main__":
    main()
