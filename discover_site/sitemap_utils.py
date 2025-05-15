import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

def fetch_sitemap_urls(base_url):
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    print(f"[INFO] Checking sitemap at {sitemap_url}")

    try:
        response = requests.get(sitemap_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[WARNING] Failed to fetch sitemap: {e}")
        return []

    try:
        root = ET.fromstring(response.content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # Check if it's a sitemap index
        sitemap_tags = root.findall(".//ns:sitemap/ns:loc", namespaces=namespace)
        if sitemap_tags:
            urls = []
            for sitemap_tag in sitemap_tags:
                child_sitemap_url = sitemap_tag.text
                print(f"[INFO] Parsing child sitemap: {child_sitemap_url}")
                try:
                    child_res = requests.get(child_sitemap_url, timeout=10)
                    child_res.raise_for_status()
                    child_root = ET.fromstring(child_res.content)
                    child_urls = [elem.text for elem in child_root.findall(".//ns:loc", namespaces=namespace)]
                    urls.extend(child_urls)
                except Exception as e:
                    print(f"[WARNING] Failed to fetch or parse child sitemap: {e}")
            return urls

        # Otherwise, treat it as a flat sitemap
        urls = [elem.text for elem in root.findall(".//ns:loc", namespaces=namespace)]
        return urls

    except ET.ParseError as e:
        print(f"[WARNING] Failed to parse sitemap XML: {e}")
        return []
