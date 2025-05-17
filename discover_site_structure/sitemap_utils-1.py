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
        urls = [elem.text for elem in root.findall(".//ns:loc", namespaces=namespace)]
        return urls
    except ET.ParseError as e:
        print(f"[WARNING] Failed to parse sitemap XML: {e}")
        return []
