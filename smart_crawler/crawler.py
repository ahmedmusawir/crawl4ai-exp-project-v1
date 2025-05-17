from __future__ import annotations
"""Markdown crawler util (stand‑alone)
-------------------------------------
✓ Reads URL list from ``outputs/discovered_pages_final.json``
✓ Prompts user to continue
✓ Crawls each page via **crawl4ai.AsyncWebCrawler**
✓ Writes one *non‑empty* ``.md`` file per page under ``outputs/pages``
    • Skips pages whose markdown is empty (logs a warning)
✓ Prints a summary when done

> No LangChain / AI calls here – just fast markdown scraping you can build on.
"""

from pathlib import Path
import asyncio
import json
# import os # os was imported but not used directly in the original relevant scope
import re
import sys
from typing import Sequence

from dotenv import load_dotenv
from rich import print

# Assuming crawl4ai is installed and these are the correct imports
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode # type: ignore

load_dotenv()

# ---------------------------------------------------------------------------
# Constants & paths
# ---------------------------------------------------------------------------
BASE_DIR = Path.cwd()
OUTPUT_DIR = BASE_DIR / "outputs"
PAGE_DIR = OUTPUT_DIR / "pages"
PAGE_DIR.mkdir(parents=True, exist_ok=True)
URL_FILE = OUTPUT_DIR / "discovered_pages_final.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# aSYNC_HEADING = re.compile(r"^#{1,3}\s+") # This was defined but not used


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-") or "root"


# ---------------------------------------------------------------------------
# Core crawl helpers
# ---------------------------------------------------------------------------

async def fetch_markdown(crawler: "AsyncWebCrawler", url: str) -> str:
    """Return cleaned markdown (may be an empty string)."""
    print(f"Attempting to fetch: [bold blue]{url}[/bold blue]")

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,  # Ensures fresh data for debugging
        page_timeout=60000,          # 60 seconds page timeout
        # You might also consider other options like:
        # wait_for_network_idle=True,
        # delay_before_return_html=2.0, # wait 2s after apparent load
    )

    try:
        result = await crawler.arun(url=url, config=run_config)
    except Exception as e:
        print(f"[red]Exception during crawler.arun for {url}: {e}[/red]")
        return ""

    if not result:
        print(f"[yellow]\u26A0\uFE0F Crawler returned no result object for:[/yellow] {url}")
        return ""

    if not result.success:
        print(f"[yellow]\u26A0\uFE0F Crawl was not successful for:[/yellow] {url}")
        if hasattr(result, 'status_code') and result.status_code:
            print(f"  Status Code: {result.status_code}")
        if hasattr(result, 'error_message') and result.error_message:
            print(f"  Error: {result.error_message}")
        return ""

    if result.markdown is None:
        print(f"[yellow]\u26A0\uFE0F result.markdown is None for:[/yellow] {url}")
        return ""

    # Access markdown attributes safely
    # fit_markdown is preferred as it's cleaner
    fit_md = getattr(result.markdown, "fit_markdown", "")
    raw_md = getattr(result.markdown, "raw_markdown", "")

    final_markdown = ""
    if fit_md:
        final_markdown = fit_md.strip()
    elif raw_md:
        print(f"[yellow]Note: fit_markdown was empty, using raw_markdown for:[/yellow] {url}")
        final_markdown = raw_md.strip()
    
    if not final_markdown:
        print(f"[yellow]\u26A0\uFE0F Both fit_markdown and raw_markdown are effectively empty for:[/yellow] {url}")
        # For deeper debugging, you could print the status or part of the raw HTML if available
        # if hasattr(result, 'html') and result.html:
        #     print(f"  Raw HTML (first 200 chars): {result.html[:200]}")
    
    return final_markdown


async def process_file(crawler: "AsyncWebCrawler", url: str) -> Path | None:
    print(f"Crawling [bold cyan]{url}[/bold cyan]")
    markdown = await fetch_markdown(crawler, url)

    if not markdown:
        # fetch_markdown now prints its own "Empty content" style messages with more detail
        # So, this message might be redundant or can be simplified
        print(f"[yellow]Skipping file creation for (empty content):[/yellow] {url}")
        return None

    name = slugify(url.replace("https://", "").replace("http://", ""))
    out_path = PAGE_DIR / f"{name}.md"
    try:
        out_path.write_text(markdown, encoding="utf‑8")
        print(f"[green]\u2714[/green]  {url}  \u2192 {out_path.relative_to(BASE_DIR)}")
        return out_path
    except Exception as e:
        print(f"[red]Error writing file for {url}: {e}[/red]")
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_urls() -> Sequence[str]:
    if not URL_FILE.exists():
        print("[red]❌  outputs/discovered_pages_final.json not found.[/red] Run discovery first.")
        sys.exit(1)

    try:
        data = json.loads(URL_FILE.read_text(encoding="utf-8"))
        return [d["url"] if isinstance(d, dict) else str(d) for d in data if d] # Ensure URLs are strings and not empty
    except json.JSONDecodeError:
        print(f"[red]❌  Error decoding JSON from {URL_FILE}.[/red]")
        sys.exit(1)
    except Exception as e:
        print(f"[red]❌  Error loading URLs from {URL_FILE}: {e}[/red]")
        sys.exit(1)


async def crawl_all(urls: Sequence[str]):
    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36" # Example common user agent
        # You can explore other BrowserConfig options if needed, e.g., proxies
    )
    # The AsyncWebCrawler should be initialized with the browser_config
    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = [process_file(crawler, u) for u in urls]
        return await asyncio.gather(*tasks, return_exceptions=True) # Added return_exceptions=True for gather


def main() -> None:  # pragma: no cover
    urls = list(load_urls())
    if not urls:
        print("[yellow]No URLs found in the input file.[/yellow]")
        return

    print("\n[bold]Target URLs[/bold] (from discovered_pages_final.json):")
    for u in urls:
        print(f" • {u}")

    try:
        proceed = input("\nProceed with markdown crawl? (y/n): ").strip().lower()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        return
        
    if proceed != "y":
        print("Aborted.")
        return

    print("\n[cyan]Starting markdown crawl…[/cyan]\n")
    
    # Ensure the event loop is managed correctly, especially if running in environments like Jupyter
    # asyncio.run() is fine for typical script usage.
    results = asyncio.run(crawl_all(urls))
    
    created_files = []
    for result_item in results:
        if isinstance(result_item, Path):
            created_files.append(result_item)
        elif isinstance(result_item, Exception):
            print(f"[red]An error occurred during a crawl task: {result_item}[/red]")
        # None results (empty content or write error) are already logged by process_file

    print("\n[bold green]✅  Crawl complete[/bold green]")
    if created_files:
        print("Successfully written files:")
        for p in created_files:
            print(f" • {p.relative_to(BASE_DIR)}")
    else:
        print("[yellow]No markdown files written. Check logs above for reasons (e.g., all pages empty or errors).[/yellow]")


if __name__ == "__main__":
    # It's good practice to ensure that `crawl4ai-setup` has been run.
    # You could add a check or reminder here if this script is distributed.
    # For example:
    # print("[info]Ensure Playwright browsers are installed by running 'crawl4ai-setup' if you haven't already.[/info]")
    main()