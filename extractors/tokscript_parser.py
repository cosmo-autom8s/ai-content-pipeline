#!/usr/bin/env python3
"""
TokScript CSV Parser — Step 5 of Content Engine

Parses TokScript CSV exports from csv_inbox/ and updates matching Links Queue
rows in Notion with transcript + metadata. If no matching row exists, creates one.

Usage:
    python extractors/tokscript_parser.py                  # Process all CSVs in csv_inbox/
    python extractors/tokscript_parser.py path/to/file.csv  # Process a specific CSV
    python extractors/tokscript_parser.py --dry-run         # Show what would be processed
"""

from __future__ import annotations

import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_LINKS_DB_ID = os.getenv("NOTION_LINKS_DB_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

CSV_INBOX = Path(__file__).parent.parent / "csv_inbox"
PROCESSED_DIR = CSV_INBOX / "processed"

MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds — doubles each retry (2, 4, 8)


def notion_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make a Notion API request with retry logic for timeouts and 5xx errors."""
    kwargs.setdefault("headers", NOTION_HEADERS)
    kwargs.setdefault("timeout", 15)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = getattr(requests, method)(url, **kwargs)
            if resp.status_code < 500:
                return resp
            # 5xx — server error, retry
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                print(f"    ⏳ Notion {resp.status_code}, retrying in {wait}s... ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                print(f"    ⏳ {type(e).__name__}, retrying in {wait}s... ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise
    return resp  # return last response even if it was 5xx


def extract_tiktok_video_id(url: str) -> str | None:
    """Extract TikTok video ID from a full URL like .../video/1234567890."""
    match = re.search(r'/video/(\d+)', url)
    return match.group(1) if match else None


def find_page_by_url(url: str) -> str | None:
    """Find a Links Queue page by its URL. Tries exact match first, then video ID match for TikTok."""
    # Try exact match first
    body = {
        "filter": {
            "property": "Link URL",
            "url": {"equals": url},
        },
        "page_size": 1,
    }
    resp = notion_request("post",
        f"https://api.notion.com/v1/databases/{NOTION_LINKS_DB_ID}/query",
        json=body,
    )
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]

    # For TikTok: shortened URLs (tiktok.com/t/XXX) won't match full URLs
    # Try to find by video ID — search for pages containing the video ID in their URL
    video_id = extract_tiktok_video_id(url)
    if video_id:
        body = {
            "filter": {
                "property": "Link URL",
                "url": {"contains": video_id},
            },
            "page_size": 1,
        }
        resp = notion_request("post",
            f"https://api.notion.com/v1/databases/{NOTION_LINKS_DB_ID}/query",
            json=body,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                return results[0]["id"]

    return None


def make_short_name(title: str) -> str:
    """Create a short name from a full caption — first 60 chars, break at word boundary."""
    if len(title) <= 60:
        return title
    truncated = title[:60]
    # Break at last space to avoid cutting mid-word
    last_space = truncated.rfind(" ")
    if last_space > 30:
        truncated = truncated[:last_space]
    return truncated + "..."


def _rich_text_blocks(text: str) -> list[dict]:
    """Split text into multiple rich_text blocks of up to 2000 chars each (Notion API limit per block)."""
    blocks = []
    for i in range(0, len(text), 2000):
        blocks.append({"text": {"content": text[i:i + 2000]}})
    return blocks


def update_notion_page(page_id: str, row: dict) -> bool:
    """Update an existing Links Queue page with TokScript data."""
    properties = {
        "Status": {"select": {"name": "transcribed"}},
    }

    if row.get("Title"):
        # Full caption goes to "Original Caption", short version to "Name"
        properties["Original Caption"] = {
            "rich_text": _rich_text_blocks(row["Title"])
        }
        properties["Name"] = {
            "title": [{"text": {"content": make_short_name(row["Title"])}}]
        }
    if row.get("Transcript"):
        properties["Transcript"] = {
            "rich_text": _rich_text_blocks(row["Transcript"])
        }
    if row.get("Views"):
        properties["Source Views"] = {
            "rich_text": [{"text": {"content": row["Views"]}}]
        }
    if row.get("Duration"):
        properties["Duration"] = {
            "rich_text": [{"text": {"content": row["Duration"]}}]
        }
    if row.get("Author"):
        properties["Author"] = {
            "rich_text": [{"text": {"content": row["Author"][:200]}}]
        }

    resp = notion_request("patch",
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": properties},
    )

    if resp.status_code == 200:
        return True
    else:
        print(f"  ❌ Notion update failed: {resp.status_code} {resp.text[:200]}")
        return False


def create_notion_page(row: dict) -> bool:
    """Create a new Links Queue page from TokScript data."""
    # Map TokScript platform to our Notion category
    platform_map = {
        "tiktok": "tiktok",
        "instagram": "reels",
        "youtube": "yt_shorts",
    }
    category = platform_map.get(row.get("Platform", "").lower(), "tiktok")

    full_title = row.get("Title", "Unknown")
    properties = {
        "Name": {"title": [{"text": {"content": make_short_name(full_title)}}]},
        "Original Caption": {"rich_text": _rich_text_blocks(full_title)},
        "Link URL": {"url": row["URL"]},
        "Category": {"select": {"name": category}},
        "Timestamp": {"date": {"start": datetime.now().isoformat()[:10]}},
        "Status": {"select": {"name": "transcribed"}},
    }

    if row.get("Transcript"):
        properties["Transcript"] = {
            "rich_text": _rich_text_blocks(row["Transcript"])
        }
    if row.get("Views"):
        properties["Source Views"] = {
            "rich_text": [{"text": {"content": row["Views"]}}]
        }
    if row.get("Duration"):
        properties["Duration"] = {
            "rich_text": [{"text": {"content": row["Duration"]}}]
        }
    if row.get("Author"):
        properties["Author"] = {
            "rich_text": [{"text": {"content": row["Author"][:200]}}]
        }

    resp = notion_request("post",
        "https://api.notion.com/v1/pages",
        json={"parent": {"database_id": NOTION_LINKS_DB_ID}, "properties": properties},
    )

    if resp.status_code == 200:
        return True
    else:
        print(f"  ❌ Notion create failed: {resp.status_code} {resp.text[:200]}")
        return False


def process_csv(csv_path: Path, dry_run: bool = False) -> tuple:
    """Process a single TokScript CSV file. Returns (processed, skipped) counts."""
    processed = 0
    skipped = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"📄 {csv_path.name}: {len(rows)} rows")

    for i, row in enumerate(rows, 1):
        url = row.get("URL", "").strip()
        title = row.get("Title", "")[:60]

        if not url:
            print(f"  {i}. ⚠ No URL, skipping")
            skipped += 1
            continue

        if dry_run:
            print(f"  {i}. {title} — {url[:60]}")
            processed += 1
            continue

        print(f"  [{i}/{len(rows)}] {title}")

        # Try to find existing page
        page_id = find_page_by_url(url)

        if page_id:
            ok = update_notion_page(page_id, row)
            if ok:
                print(f"    ✅ Updated existing row → transcribed")
                processed += 1
            else:
                skipped += 1
        else:
            ok = create_notion_page(row)
            if ok:
                print(f"    ✅ Created new row → transcribed")
                processed += 1
            else:
                skipped += 1

    return processed, skipped


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if args:
        # Process specific CSV
        csv_path = Path(args[0])
        if not csv_path.exists():
            print(f"❌ File not found: {csv_path}")
            return
        processed, skipped = process_csv(csv_path, dry_run)
    else:
        # Process all CSVs in csv_inbox/
        if not CSV_INBOX.exists():
            print(f"❌ csv_inbox/ directory not found")
            return

        csv_files = sorted(CSV_INBOX.glob("*.csv"))
        if not csv_files:
            print("✅ No CSV files in csv_inbox/")
            return

        print(f"🔍 Found {len(csv_files)} CSV file(s) in csv_inbox/\n")

        total_processed = 0
        total_skipped = 0

        for csv_path in csv_files:
            processed, skipped = process_csv(csv_path, dry_run)
            total_processed += processed
            total_skipped += skipped

            # Move processed CSV to processed/ subfolder
            if not dry_run and processed > 0:
                PROCESSED_DIR.mkdir(exist_ok=True)
                dest = PROCESSED_DIR / csv_path.name
                csv_path.rename(dest)
                print(f"  📂 Moved to csv_inbox/processed/")

            print()

        print(f"✅ Done: {total_processed} processed, {total_skipped} skipped")
        return

    if not dry_run:
        print(f"\n✅ Done: {processed} processed, {skipped} skipped")


if __name__ == "__main__":
    main()
