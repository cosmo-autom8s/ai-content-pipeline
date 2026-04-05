#!/usr/bin/env python3
"""
Upload Tokscript CSV export to Notion.

Usage:
    python3 upload_to_notion.py /path/to/tokscript_export.csv

This script:
1. Reads the Tokscript CSV export (handles commas in text fields)
2. Uploads each video to the Notion database via API
3. Clears pending_links.txt after successful upload
"""

import csv
import sys
import os
import requests
from datetime import datetime
from pathlib import Path

# ============ CONFIGURATION ============
NOTION_API_KEY = "REDACTED"  # You'll need to add this
NOTION_DATABASE_ID = "2ffa44c6f32f8090a6f5d4dc01d76792"
PENDING_LINKS_FILE = Path(__file__).parent / "links" / "pending_shorts.txt"
# =======================================

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


def parse_csv(filepath: str) -> list[dict]:
    """Parse Tokscript CSV export into list of video records."""
    videos = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            video = {
                "title": row.get("Title", "").strip(),
                "platform": row.get("Platform", "").strip().lower(),
                "status": row.get("Status", "").strip().lower(),
                "date": row.get("Date", "").strip(),
                "url": row.get("URL", "").strip(),
                "duration": row.get("Duration", "").strip(),
                "author": row.get("Author", "").strip(),
                "views": row.get("Views", "").strip(),
                "video_id": row.get("VideoID", "").strip(),
                "transcript": row.get("Transcript", "").strip(),
            }
            
            # Only include completed videos with transcripts
            if video["status"] == "complete" and video["transcript"]:
                videos.append(video)
    
    return videos


def convert_date(date_str: str) -> str:
    """Convert date string to ISO format for Notion."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    
    # Try common formats
    formats = [
        "%m/%d/%Y",   # 2/6/2026
        "%Y-%m-%d",   # 2026-02-06
        "%d/%m/%Y",   # 6/2/2026
        "%m/%d/%y",   # 2/6/26
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return datetime.now().strftime("%Y-%m-%d")


def upload_to_notion(video: dict) -> tuple[bool, str]:
    """Upload a single video to Notion. Returns (success, message)."""
    
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }
    
    # Build the properties payload
    properties = {
        "Name": {
            "title": [{"text": {"content": video["title"] or f"Video from {video['author']}"}}]
        },
        "Transcript": {
            "rich_text": [{"text": {"content": video["transcript"][:2000]}}]  # Notion limit
        },
        "Duration": {
            "rich_text": [{"text": {"content": video["duration"]}}]
        },
        "Views": {
            "rich_text": [{"text": {"content": video["views"]}}]
        },
        "VideoID": {
            "rich_text": [{"text": {"content": video["video_id"]}}]
        },
        "URL": {
            "url": video["url"] if video["url"] else None
        },
        "Date": {
            "date": {"start": convert_date(video["date"])}
        },
    }

    # Author is a select field
    if video["author"]:
        properties["Author"] = {"select": {"name": video["author"]}}
    
    # Add Platform if valid
    if video["platform"] in ["youtube", "tiktok", "instagram"]:
        properties["Platform"] = {"select": {"name": video["platform"]}}
    
    # Add Status if valid
    if video["status"] == "complete":
        properties["Status"] = {"select": {"name": video["status"]}}
    
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }
    
    try:
        response = requests.post(NOTION_API_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            return True, "Success"
        else:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
    
    except Exception as e:
        return False, str(e)


def clear_pending_links():
    """Clear the pending links file."""
    if PENDING_LINKS_FILE.exists():
        PENDING_LINKS_FILE.unlink()
        print(f"🗑️  Cleared {PENDING_LINKS_FILE}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 upload_to_notion.py /path/to/tokscript_export.csv")
        print("\nExample:")
        print("  python3 upload_to_notion.py ~/Downloads/bulk_processing_export.csv")
        sys.exit(1)
    
    # Check API key
    if NOTION_API_KEY == "YOUR_NOTION_API_KEY_HERE":
        print("❌ Error: You need to add your Notion API key to this script.")
        print("\nTo get your API key:")
        print("1. Go to https://www.notion.so/my-integrations")
        print("2. Create a new integration (or use existing)")
        print("3. Copy the 'Internal Integration Token'")
        print("4. Open this script and replace YOUR_NOTION_API_KEY_HERE with your token")
        print("5. Make sure your Notion database is shared with the integration!")
        sys.exit(1)
    
    csv_path = os.path.expanduser(sys.argv[1])
    
    print(f"📂 Reading CSV: {csv_path}")
    
    try:
        videos = parse_csv(csv_path)
    except FileNotFoundError:
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error parsing CSV: {e}")
        sys.exit(1)
    
    if not videos:
        print("⚠️  No completed videos with transcripts found in CSV.")
        sys.exit(0)
    
    print(f"📊 Found {len(videos)} videos to upload\n")
    
    # Upload each video
    success_count = 0
    fail_count = 0
    
    for i, video in enumerate(videos, 1):
        title = video["title"][:40] or video["url"][:40]
        print(f"[{i}/{len(videos)}] Uploading: {title}...", end=" ")
        
        success, message = upload_to_notion(video)
        
        if success:
            print("✅")
            success_count += 1
        else:
            print(f"❌ {message}")
            fail_count += 1
    
    print()
    print("=" * 40)
    print(f"✅ Uploaded: {success_count}")
    if fail_count:
        print(f"❌ Failed: {fail_count}")
    
    # Clear pending links if all succeeded
    if fail_count == 0:
        clear_pending_links()
        print("\n🎉 All done! Ready for Part C (Content Generation).")
    else:
        print(f"\n⚠️  Some uploads failed. Pending links NOT cleared.")


if __name__ == "__main__":
    main()
