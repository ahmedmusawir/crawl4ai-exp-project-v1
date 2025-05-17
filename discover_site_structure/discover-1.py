import sys
import json
import argparse
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

output_path = 'outputs/discovered_pages.json'

def is_valid_link(href, domain):
    if not href:
        return False
    if href.startswith("mailto:") or href.startswith("tel:"):
        return False
    parsed = urlparse(href)
    return (not parsed.netloc or parsed.netloc == domain) and not parsed.fragment

def normalize_link(href, base_url):
    return urljoin(base_url, href.split("#")[0].split("?")[0])

def extract_internal_links(base_url):
    domain = urlparse(base_url).netloc
    print(f"[INFO] Crawling: {base_url}")

    try:
        res = requests.get(base_url, timeout=10)
        res.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch {base_url}: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    anchors = soup.find_all("a")

    links = set()
    for tag in anchors:
        href = tag.get("href")
        if is_valid_link(href, domain):
            full_url = normalize_link(href, base_url)
            if full_url.startswith(base_url):
                links.add(full_url)

    return sorted(links)

def write_to_json(urls, output_path):
    data = [ {"url": url} for url in urls ]
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[SUCCESS] Saved {len(data)} links to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Discover internal links on a website")
    parser.add_argument("url", help="Root URL of the website to crawl")
    args = parser.parse_args()

    links = extract_internal_links(args.url)
    write_to_json(links, output_path)

    with open(output_path, "r") as f:
        print("\n[INFO] Discovered Pages:")
        for entry in json.load(f):
            print(f"- {entry['url']}")    

if __name__ == "__main__":
    main()
