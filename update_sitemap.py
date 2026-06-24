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
    "https://gasheads.org/",
    "https://gasheads.org/board/2/gas-guzzler",
    "https://gasheads.org/board/3/general-football-chat",
    "https://gasheads.org/board/20/match-day-threads",
    "https://gasheads.org/board/38/england-games-news",
    "https://gasheads.org/board/40/world-cup-2026-general-news",
    "https://gasheads.org/board/6/cricket-lovers",
    "https://gasheads.org/board/10/all-sports",
    "https://gasheads.org/board/7/rugby-chat",
    "https://gasheads.org/page/sitemap2",
    "https://gasheads.org/page/volunteer",
    "https://gasheads.org/page/contact-us",
]

STATE_FILE = ".state.json"
SITEMAP_FILE = "sitemap.xml"
TODAY = datetime.date.today().isoformat()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

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
    """Fetch HTML with browser headers to avoid ProBoards bot filtering."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"ERROR fetching {url}: {e}")
        return None


def extract_board_timestamp(html):
    """Extract newest <time datetime=""> tag from a ProBoards board page."""
    soup = BeautifulSoup(html, "html.parser")
    time_tags = soup.select("time")
    timestamps = [t.get("datetime") for t in time_tags if t.get("datetime")]
    return max(timestamps) if timestamps else None


def hash_page(html):
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def ensure_url_in_sitemap(root, url, ns):
    """Ensure URL exists in sitemap; create entry if missing."""
    for url_node in root.findall("ns:url", ns):
        loc = url_node.find("ns:loc", ns)
        if loc is not None and loc.text == url:
            return url_node

    # Create new <url> entry
    url_node = ET.SubElement(root, "url")
    loc = ET.SubElement(url_node, "loc")
    loc.text = url
    lastmod = ET.SubElement(url_node, "lastmod")
    lastmod.text = TODAY
    return url_node


def remove_dead_url(root, url, ns):
    """Remove a URL from the sitemap when it becomes unreachable."""
    for url_node in root.findall("ns:url", ns):
        loc = url_node.find("ns:loc", ns)
        if loc is not None and loc.text == url:
            root.remove(url_node)
            print(f"REMOVED DEAD URL: {url}")
            return True
    return False


def update_sitemap(changed_urls, new_state):
    tree = ET.parse(SITEMAP_FILE)
    root = tree.getroot()
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    for url in changed_urls:
        if new_state.get(url) is None:
            remove_dead_url(root, url, ns)
            continue

        url_node = ensure_url_in_sitemap(root, url, ns)
        lastmod = url_node.find("lastmod")
        if lastmod is None:
            lastmod = ET.SubElement(url_node, "lastmod")
        lastmod.text = TODAY

    tree.write(SITEMAP_FILE, encoding="utf-8", xml_declaration=True)


# -----------------------------
# REPORT GENERATION
# -----------------------------
def build_summary(changed_urls, state, new_state):
    lines = []
    lines.append("Gasheads.org Daily Sitemap Summary")
    lines.append("----------------------------------")
    lines.append(f"Date: {TODAY}")
    lines.append(f"Total monitored URLs: {len(MONITORED_URLS)}")
    lines.append("")

    if changed_urls:
        lines.append("Changes detected:")
        for url in changed_urls:
            lines.append(f"- {url}")
            lines.append(f"  Old: {state.get(url)}")
            lines.append(f"  New: {new_state.get(url)}")
        lines.append("")
    else:
        lines.append("No changes detected today.")
        lines.append("")

    dead = [u for u in changed_urls if new_state.get(u) is None]
    if dead:
        lines.append("Dead URLs removed:")
        for url in dead:
            lines.append(f"- {url}")
        lines.append("")

    return "\n".join(lines)


def build_diff_viewer(changed_urls, state, new_state):
    html = []
    html.append("<html><head><title>Gasheads Diff Viewer</title></head><body>")
    html.append("<h1>Gasheads.org Change Report</h1>")
    html.append(f"<p>Date: {TODAY}</p>")
    html.append("<table border='1' cellpadding='6'>")
    html.append("<tr><th>URL</th><th>Old</th><th>New</th><th>Status</th></tr>")

    for url in MONITORED_URLS:
        old = state.get(url)
        new = new_state.get(url)

        if new is None:
            status = "<b style='color:red'>DEAD</b>"
        elif old != new:
            status = "<b style='color:green'>CHANGED</b>"
        else:
            status = "No change"

        html.append(
            f"<tr><td>{url}</td><td>{old}</td><td>{new}</td><td>{status}</td></tr>"
        )

    html.append("</table></body></html>")
    return "\n".join(html)


# -----------------------------
# MAIN LOGIC
# -----------------------------
def main():
    print("Loading previous state...")
    state = load_state()
    new_state = {}
    changed_urls = []

    for url in MONITORED_URLS:
        print(f"\nChecking {url}...")
        html = fetch_html(url)

        if html is None:
            print(f"DEAD URL DETECTED: {url}")
            new_state[url] = None
            changed_urls.append(url)
            continue

        print("Fetched HTML sample:", html[:200].replace("\n", " "))

        if "/board/" in url:
            ts = extract_board_timestamp(html)
            print("Extracted timestamp:", ts)
            new_state[url] = ts
        else:
            page_hash = hash_page(html)
            print("Page hash:", page_hash)
            new_state[url] = page_hash

        old = state.get(url)
        new = new_state[url]

        print("Old state:", old)
        print("New state:", new)

        if old != new:
            print("CHANGE DETECTED:", url)
            changed_urls.append(url)
        else:
            print("No change.")

    if changed_urls:
        print("\nUpdating sitemap for changed URLs...")
        update_sitemap(changed_urls, new_state)
    else:
        print("\nNo changes detected.")

    save_state(new_state)
    print("State saved.")

    summary = build_summary(changed_urls, state, new_state)
    with open("daily_summary.txt", "w") as f:
        f.write(summary)

    diff_html = build_diff_viewer(changed_urls, state, new_state)
    with open("diff_viewer.html", "w") as f:
        f.write(diff_html)

    print("\n=== DAILY SUMMARY ===")
    print(summary)


if __name__ == "__main__":
    main()
