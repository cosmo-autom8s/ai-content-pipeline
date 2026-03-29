#!/usr/bin/env python3
"""
Evening Orchestrator — Step 7 of Content Engine

Runs the full evening pipeline:
1. Query Links Queue for status=pending
2. Process YouTube links through transcript extractor
3. Print summary of what was processed and what needs manual attention
4. Optionally trigger ideation listing

Usage:
    python orchestrator.py              # Run full pipeline
    python orchestrator.py --dry-run    # Show what would be processed
    python orchestrator.py --status     # Show pipeline status overview
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from extractors.youtube import (
    extract_video_id,
    process_link,
    query_pending_youtube_links,
)
from extractors.tokscript_parser import CSV_INBOX
from engines.classifier import classify_all_transcribed

# Load .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_LINKS_DB_ID = os.getenv("NOTION_LINKS_DB_ID")
NOTION_IDEAS_DB_ID = os.getenv("NOTION_IDEAS_DB_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# Categories that can be auto-transcribed vs need manual work
AUTO_CATEGORIES = {"podcast", "long_form"}
MANUAL_CATEGORIES = {"short_form"}  # needs TokScript
SKIP_CATEGORIES = {"carousel", "x_post", "linkedin", "reddit"}


def query_all_pending() -> list[dict]:
    """Query all pending links from Notion."""
    results = []
    has_more = True
    start_cursor = None

    while has_more:
        body = {
            "filter": {
                "property": "Status",
                "select": {"equals": "pending"},
            },
            "page_size": 100,
        }
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_LINKS_DB_ID}/query",
            headers=NOTION_HEADERS,
            json=body,
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"Error querying Notion: {resp.status_code} {resp.text[:200]}")
            return []

        data = resp.json()
        for page in data.get("results", []):
            props = page["properties"]
            name_parts = props.get("Name", {}).get("title", [])
            name = name_parts[0]["plain_text"] if name_parts else ""
            category_obj = props.get("Category", {}).get("select")
            category = category_obj["name"] if category_obj else ""
            url = props.get("Link URL", {}).get("url", "")

            results.append({
                "page_id": page["id"],
                "name": name,
                "url": url,
                "category": category,
            })

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return results


def count_by_status(db_id: str, status: str) -> int:
    """Count pages with a given status in a database."""
    body = {
        "filter": {
            "property": "Status",
            "select": {"equals": status},
        },
        "page_size": 1,
    }
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=NOTION_HEADERS,
        json=body,
        timeout=15,
    )
    if resp.status_code != 200:
        return -1
    # Notion doesn't return total count easily, so we need to paginate
    # For status overview, approximate with has_more check
    data = resp.json()
    if not data.get("results"):
        return 0
    # Do a full count
    count = 0
    has_more = True
    start_cursor = None
    while has_more:
        body["page_size"] = 100
        if start_cursor:
            body["start_cursor"] = start_cursor
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=NOTION_HEADERS,
            json=body,
            timeout=15,
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        count += len(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return count


def show_status():
    """Show pipeline status overview."""
    print("Pipeline Status Overview")
    print("=" * 50)

    print("\nLinks Queue:")
    for status in ["pending", "transcribed", "processed", "archived"]:
        count = count_by_status(NOTION_LINKS_DB_ID, status)
        print(f"  {status}: {count}")

    print("\nContent Ideas:")
    for status in ["new", "queued", "filming_today", "filmed", "captioned", "posted", "archived"]:
        count = count_by_status(NOTION_IDEAS_DB_ID, status)
        if count > 0:
            print(f"  {status}: {count}")

    # Check csv_inbox
    csv_files = list(CSV_INBOX.glob("*.csv")) if CSV_INBOX.exists() else []
    if csv_files:
        print(f"\nCSV Inbox: {len(csv_files)} file(s) waiting")
        for f in csv_files:
            print(f"  {f.name}")

    print()


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args

    if "--status" in args:
        show_status()
        return

    print("Evening Pipeline")
    print("=" * 50)
    print()

    # Step 1: Check for CSVs in inbox
    csv_files = list(CSV_INBOX.glob("*.csv")) if CSV_INBOX.exists() else []
    if csv_files:
        print(f"CSV Inbox: {len(csv_files)} TokScript export(s) found")
        if not dry_run:
            from extractors.tokscript_parser import process_csv, PROCESSED_DIR
            for csv_path in csv_files:
                processed, skipped = process_csv(csv_path)
                if processed > 0:
                    PROCESSED_DIR.mkdir(exist_ok=True)
                    dest = PROCESSED_DIR / csv_path.name
                    csv_path.rename(dest)
                    print(f"  Moved to csv_inbox/processed/")
        else:
            for f in csv_files:
                print(f"  Would process: {f.name}")
        print()

    # Step 2: Query pending links
    print("Querying pending links...")
    pending = query_all_pending()

    if not pending:
        print("No pending links.\n")
    else:
        # Categorize
        youtube_links = []
        manual_links = []
        skipped_links = []

        for link in pending:
            cat = link["category"]
            has_yt = extract_video_id(link["url"]) is not None

            if has_yt and cat in AUTO_CATEGORIES:
                youtube_links.append(link)
            elif cat in MANUAL_CATEGORIES:
                manual_links.append(link)
            elif has_yt:
                # YouTube URL in a non-auto category — still try
                youtube_links.append(link)
            else:
                skipped_links.append(link)

        print(f"\nFound {len(pending)} pending links:")
        print(f"  YouTube (auto-extract): {len(youtube_links)}")
        print(f"  Short-form (needs TokScript): {len(manual_links)}")
        print(f"  Skipped (no extractor): {len(skipped_links)}")
        print()

        # Step 3: Process YouTube links
        if youtube_links:
            print(f"Processing {len(youtube_links)} YouTube link(s)...")
            print()
            success = 0
            for i, link in enumerate(youtube_links, 1):
                print(f"[{i}/{len(youtube_links)}] {link['name'][:50]} — {link['url'][:60]}")
                if dry_run:
                    print("  (dry run — would extract transcript)")
                else:
                    if process_link(link["page_id"], link["url"], link["name"]):
                        success += 1
                print()
            if not dry_run:
                print(f"YouTube extraction: {success}/{len(youtube_links)} successful")
            print()

        # Step 4: Report manual work needed
        if manual_links:
            print("Manual attention needed (TokScript):")
            for link in manual_links:
                print(f"  {link['name'][:60]} — {link['url'][:60]}")
            print(f"\n  Export transcripts via TokScript, drop CSV in csv_inbox/")
            print(f"  Then run: python extractors/tokscript_parser.py")
            print()

        if skipped_links:
            print(f"Skipped ({len(skipped_links)} links — no extractor available):")
            for link in skipped_links[:5]:
                print(f"  [{link['category']}] {link['name'][:50]} — {link['url'][:50]}")
            if len(skipped_links) > 5:
                print(f"  ... and {len(skipped_links) - 5} more")
            print()

    # Step 5: Classify newly transcribed links
    print("=" * 50)
    print("Classifying transcribed links...")
    if not dry_run:
        classified_count = classify_all_transcribed()
        print(f"\nClassification: {classified_count} links classified")
    else:
        classified_count = classify_all_transcribed(dry_run=True)
        print(f"\nClassification: {classified_count} links would be classified")
    print()

    # Step 6: Summary
    print("=" * 50)
    print("Next steps:")
    print("  1. Review classified links in Notion 'Classified' view")
    print("  2. Tag links for ideation: python engines/ideation.py --list")
    print("  3. Generate ideas: /ca-ideate")
    print("  4. Review Morning Menu in Notion")
    print()


if __name__ == "__main__":
    main()
