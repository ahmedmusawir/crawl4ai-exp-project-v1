import asyncio
from crawl4ai import AsyncWebCrawler


async def main():
    url = "https://cyberizegroup.com/the-ultimate-seo-content-template-how-to-create-seo-friendly-content-in-minutes/"
    output_path = "output.md"

    # Create the async crawler instance
    async with AsyncWebCrawler() as crawler:
        print(f"\nCrawling {url}...")

        # Run the crawler
        result = await crawler.arun(url=url)

        # Save markdown to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.markdown)

        print(f"\nMarkdown content written to: {output_path}\n")
    

        # Output markdown result to terminal
        # print("\n--- Markdown Output ---\n")
        # print(result.markdown)

        # You could also access raw HTML or structured metadata like:
        # print(result.html)
        # print(result.metadata)


# Run the main async function
if __name__ == "__main__":
    asyncio.run(main())
