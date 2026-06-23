import requests
from bs4 import BeautifulSoup
import hashlib
import json
import datetime
import os
import xml.etree.ElementTree as ET

# -----------------------------
# CONFIGURATION
# -----------------------------
MONITORED_URLS = [
    "https://gasheads.org/board/2/gas-guzzler",
    "https://gasheads.org/board/3/general-football-chat",
    "https://gasheads.org/",
    "https://gasheads.org/board/20/match-day-threads",
    "https://gasheads.org/page/sitemap2",
    "https://gasheads.org/page/volunteer",
    "https://gasheads.org/page/contact-us"
]

STATE_FILE = ".state.json"
SITEMAP_FILE = "sitemap.xml"

TODAY = datetime.date.today().isoformat()


# -----------------------------
# HELPERS
# -----------------------------
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_html(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.text


def extract_board_timestamp(html):
    """
    Gasheads.org (ProBoards) board pages show a "last updated" timestamp
    in the thread list. We extract the most recent timestamp.
    """
    soup = BeautifulSoup(html, "html.parser")
    time_tags = soup.select("time")

    if not time_tags:
        return None

    # Use the newest timestamp on the page
    timestamps = [t.get("datetime") for t in time_tags if t.get("datetime")]
    return max(timestamps) if timestamps else None


def hash_page(html):
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def update_sitemap(urls_to_update):
    tree = ET.parse(SITEMAP_FILE)
    root = tree.getroot()

    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    for url in urls_to_update:
        for url_node in root.findall("ns:url", ns):
            loc = url_node.find("ns:loc", ns)
            lastmod = url_node.find("ns:lastmod", ns)

            if loc is not None and loc.text == url:
                if lastmod is None:
                    lastmod = ET.SubElement(url_node, "lastmod")
                lastmod.text = TODAY

    tree.write(SITEMAP_FILE, encoding="utf-8", xml_declaration=True)


# -----------------------------
# MAIN LOGIC
# -----------------------------
def main():
    print("Loading previous state...")
    state = load_state()
    new_state = {}
    changed_urls = []

    for url in MONITORED_URLS:
        print(f"Checking {url}...")
        html = fetch_html(url)

        if "/board/" in url:
            # Board page → use timestamp
            ts = extract_board_timestamp(html)
            new_state[url] = ts
            if ts != state.get(url):
                changed_urls.append(url)

        else:
            # Static page → use hash
            h = hash_page(html)
            new_state[url] = h
            if h != state.get(url):
                changed_urls.append(url)

    if not changed_urls:
        print("No changes detected.")
        save_state(new_state)
        return

    print("Changes detected in:")
    for u in changed_urls:
        print(" -", u)

    print("Updating sitemap...")
    update_sitemap(changed_urls)

    print("Saving new state...")
    save_state(new_state)

    print("Done. Changes will be committed by GitHub Actions.")


if __name__ == "__main__":
    main()
