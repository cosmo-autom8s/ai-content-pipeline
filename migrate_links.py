#!/usr/bin/env python3
"""One-time migration: import pending links from text files into Notion Links Queue."""

import os
import re
import time
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_LINKS_DB_ID = os.getenv("NOTION_LINKS_DB_ID")
NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}

# Map file names to Notion category values
FILE_CATEGORY_MAP = {
    "pending_shorts.txt": "short_form",
    "pending_carousels.txt": "carousel",
    "pending_podcasts.txt": "podcast",
    "pending_x.txt": "x_post",
    "pending_linkedin.txt": "linkedin",
    "pending_reddit.txt": "reddit",
    "pending_links.txt": "short_form",  # Legacy file, mostly TikTok/YT shorts
}

URL_PATTERN = re.compile(r'https?://\S+')


def extract_url_and_notes(line):
    """Extract the first URL and any remaining text as notes."""
    line = line.strip()
    if not line:
        return None, None
    match = URL_PATTERN.search(line)
    if not match:
        return None, None
    url = match.group(0)
    # Notes = everything after the URL
    notes = line[match.end():].strip()
    return url, notes if notes else None


def create_notion_row(url, category, notes=None):
    """Create a row in the Links Queue Notion database."""
    # Use domain as a short name
    domain_match = re.search(r'//(?:www\.)?([^/]+)', url)
    name = domain_match.group(1) if domain_match else url[:50]

    properties = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Link URL": {"url": url},
        "Category": {"select": {"name": category}},
        "Timestamp": {"date": {"start": datetime.now().isoformat()[:10]}},
        "Status": {"select": {"name": "pending"}},
    }
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes[:2000]}}]}

    payload = {
        "parent": {"database_id": NOTION_LINKS_DB_ID},
        "properties": properties,
    }

    response = requests.post(NOTION_API_URL, headers=HEADERS, json=payload)
    return response.status_code == 200


def main():
    links_dir = Path(__file__).parent / "links"
    seen_urls = set()
    total = 0
    success = 0
    skipped_dupes = 0

    for filename, category in FILE_CATEGORY_MAP.items():
        filepath = links_dir / filename
        if not filepath.exists():
            print(f"  Skipping {filename} (not found)")
            continue

        lines = filepath.read_text().strip().splitlines()
        print(f"\n📁 {filename} ({len(lines)} lines) → category: {category}")

        for line in lines:
            url, notes = extract_url_and_notes(line)
            if not url:
                continue

            # Deduplicate
            if url in seen_urls:
                skipped_dupes += 1
                print(f"  ⏭ Duplicate: {url[:60]}...")
                continue
            seen_urls.add(url)

            total += 1
            ok = create_notion_row(url, category, notes)
            if ok:
                success += 1
                note_flag = " 📝" if notes else ""
                print(f"  ✓ {url[:60]}...{note_flag}")
            else:
                print(f"  ✗ FAILED: {url[:60]}...")

            # Rate limit: Notion API allows ~3 requests/second
            time.sleep(0.35)

    print(f"\n{'='*50}")
    print(f"Migration complete: {success}/{total} links imported")
    print(f"Duplicates skipped: {skipped_dupes}")


if __name__ == "__main__":
    main()
