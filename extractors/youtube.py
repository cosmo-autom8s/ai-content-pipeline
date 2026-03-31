#!/usr/bin/env python3
"""
YouTube Transcript Extractor — Step 4 of Content Engine

Extracts transcripts + metadata from YouTube URLs and updates matching
Links Queue rows in Notion. Can process a single URL or all pending
YouTube links from the database.

Usage:
    python extractors/youtube.py                    # Process all pending YouTube links
    python extractors/youtube.py URL                # Process a single URL
    python extractors/youtube.py --dry-run          # Show what would be processed
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

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

YOUTUBE_ID_PATTERNS = [
    re.compile(r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtu\.be/([a-zA-Z0-9_-]{11})"),
]


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    for pattern in YOUTUBE_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def get_transcript(video_id: str) -> str | None:
    """Fetch transcript text using youtube-transcript-api."""
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=["en"])
        lines = [snippet.text for snippet in transcript.snippets]
        return " ".join(lines)
    except Exception as e:
        print(f"  ⚠ Transcript fetch failed: {e}")
        return None


def get_metadata(url: str) -> dict:
    """Fetch video metadata using yt-dlp (no download)."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", "--no-playlist", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"  ⚠ yt-dlp error: {result.stderr[:200]}")
            return {}
        data = json.loads(result.stdout)
        return {
            "title": data.get("title", ""),
            "views": str(data.get("view_count", "")),
            "duration": str(data.get("duration_string", data.get("duration", ""))),
            "author": data.get("uploader", data.get("channel", "")),
            "likes": str(data.get("like_count", "")),
            "description": data.get("description", ""),
        }
    except subprocess.TimeoutExpired:
        print("  ⚠ yt-dlp timed out")
        return {}
    except Exception as e:
        print(f"  ⚠ Metadata fetch failed: {e}")
        return {}


def query_pending_youtube_links() -> list[dict]:
    """Query Notion for pending links that are YouTube URLs."""
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
            print(f"❌ Notion query failed: {resp.status_code} {resp.text[:200]}")
            return []

        data = resp.json()
        for page in data.get("results", []):
            props = page["properties"]
            url_obj = props.get("Link URL", {}).get("url")
            if url_obj and extract_video_id(url_obj):
                name_parts = props.get("Name", {}).get("title", [])
                name = name_parts[0]["plain_text"] if name_parts else ""
                results.append({
                    "page_id": page["id"],
                    "url": url_obj,
                    "name": name,
                })

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return results


def update_notion_page(page_id: str, transcript: str, metadata: dict) -> bool:
    """Update a Links Queue page with transcript + metadata, set status=transcribed."""
    properties = {
        "Status": {"select": {"name": "transcribed"}},
    }

    if transcript:
        # Notion rich_text max is 2000 chars per block
        properties["Transcript"] = {
            "rich_text": [{"text": {"content": transcript[:2000]}}]
        }

    if metadata.get("title"):
        properties["Name"] = {
            "title": [{"text": {"content": metadata["title"][:200]}}]
        }
    if metadata.get("views"):
        properties["Source Views"] = {
            "rich_text": [{"text": {"content": metadata["views"]}}]
        }
    if metadata.get("likes"):
        properties["Source Likes"] = {
            "rich_text": [{"text": {"content": metadata["likes"]}}]
        }
    if metadata.get("duration"):
        properties["Duration"] = {
            "rich_text": [{"text": {"content": metadata["duration"]}}]
        }
    if metadata.get("author"):
        properties["Author"] = {
            "rich_text": [{"text": {"content": metadata["author"][:200]}}]
        }
    if metadata.get("description"):
        properties["Original Caption"] = {
            "rich_text": [{"text": {"content": metadata["description"][:2000]}}]
        }

    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json={"properties": properties},
        timeout=15,
    )

    if resp.status_code == 200:
        return True
    else:
        print(f"  ❌ Notion update failed: {resp.status_code} {resp.text[:200]}")
        return False


def process_link(page_id: str, url: str, name: str) -> bool:
    """Process a single YouTube link: extract transcript + metadata, update Notion."""
    video_id = extract_video_id(url)
    if not video_id:
        print(f"  ⚠ Not a YouTube URL: {url}")
        return False

    print(f"  📥 Fetching transcript for {video_id}...")
    transcript = get_transcript(video_id)

    print(f"  📊 Fetching metadata...")
    metadata = get_metadata(url)

    title = metadata.get("title", name)
    views = metadata.get("views", "?")
    duration = metadata.get("duration", "?")

    if transcript:
        words = len(transcript.split())
        print(f"  ✅ Got transcript: {words} words | {title} | {views} views | {duration}")
    else:
        print(f"  ⚠ No transcript available | {title} | {views} views | {duration}")

    if page_id:
        ok = update_notion_page(page_id, transcript, metadata)
        if ok:
            print(f"  📋 Notion updated → transcribed")
        return ok

    return True


def find_page_by_url(url: str) -> str | None:
    """Find a Links Queue page by its URL."""
    body = {
        "filter": {
            "property": "Link URL",
            "url": {"equals": url},
        },
        "page_size": 1,
    }
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_LINKS_DB_ID}/query",
        headers=NOTION_HEADERS,
        json=body,
        timeout=15,
    )
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]
    return None


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if args:
        # Single URL mode
        url = args[0]
        print(f"🎬 Processing single URL: {url}")
        page_id = find_page_by_url(url)
        if not page_id:
            print("  ⚠ URL not found in Links Queue — extracting without Notion update")
        process_link(page_id, url, "")
    else:
        # Batch mode — process all pending YouTube links
        print("🔍 Querying Notion for pending YouTube links...")
        links = query_pending_youtube_links()

        if not links:
            print("✅ No pending YouTube links to process.")
            return

        print(f"📋 Found {len(links)} pending YouTube links\n")

        if dry_run:
            for i, link in enumerate(links, 1):
                print(f"  {i}. {link['name'][:50]} — {link['url']}")
            print(f"\nRun without --dry-run to process these.")
            return

        success = 0
        for i, link in enumerate(links, 1):
            print(f"[{i}/{len(links)}] {link['name'][:50]} — {link['url']}")
            if process_link(link["page_id"], link["url"], link["name"]):
                success += 1
            print()

        print(f"✅ Done: {success}/{len(links)} processed successfully")


if __name__ == "__main__":
    main()
