#!/usr/bin/env python3
"""
Spotify → YouTube Converter — Content Engine

Takes pending podcast links that are Spotify URLs, finds the matching YouTube
version, and creates a new Links Queue row with the YouTube URL. The original
Spotify row gets status=converted and is enriched with episode title + metadata.

Usage:
    python extractors/spotify_to_youtube.py                # Process all pending Spotify podcasts
    python extractors/spotify_to_youtube.py URL            # Process a single Spotify URL
    python extractors/spotify_to_youtube.py --dry-run      # Show what would be processed
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

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


def clean_spotify_url(url: str) -> str:
    """Strip tracking params from Spotify URLs for cleaner oEmbed lookups."""
    # Keep just the base: https://open.spotify.com/episode/EPISODE_ID
    match = re.match(r'(https?://open\.spotify\.com/episode/[a-zA-Z0-9]+)', url)
    return match.group(1) if match else url


def get_spotify_metadata(spotify_url: str) -> dict:
    """Get episode metadata from Spotify's free oEmbed endpoint (no auth needed)."""
    clean_url = clean_spotify_url(spotify_url)
    try:
        resp = requests.get(
            "https://open.spotify.com/oembed",
            params={"url": clean_url},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # oEmbed returns: title, thumbnail_url, html (embed), provider_name
            raw_title = data.get("title", "")
            # Try to split "Episode Title - Show Name" pattern
            # Spotify oEmbed title format varies but often includes show name
            return {
                "title": raw_title,
                "thumbnail": data.get("thumbnail_url", ""),
                "provider": data.get("provider_name", "Spotify"),
            }
        else:
            print(f"  ⚠ Spotify oEmbed failed: {resp.status_code}")
            return {}
    except Exception as e:
        print(f"  ⚠ Spotify metadata error: {e}")
        return {}


def search_youtube(query: str) -> dict | None:
    """Search YouTube for a matching video using yt-dlp. Returns best match metadata."""
    try:
        # Search for top 3 results, pick the best one
        result = subprocess.run(
            [
                "yt-dlp",
                f"ytsearch3:{query}",
                "--dump-json",
                "--no-download",
                "--no-playlist",
                "--flat-playlist",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"  ⚠ yt-dlp search error: {result.stderr[:200]}")
            return None

        # yt-dlp outputs one JSON object per line
        results = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if not results:
            print("  ⚠ No YouTube results found")
            return None

        # Pick the best result — prefer longer videos (podcasts are usually 10+ min)
        # and results that have substantial view counts
        best = results[0]
        for r in results:
            duration = r.get("duration") or 0
            best_duration = best.get("duration") or 0
            # Prefer videos longer than 5 minutes (podcast episodes)
            if duration > 300 and best_duration < 300:
                best = r
            # Among long videos, prefer higher view count
            elif duration > 300 and best_duration > 300:
                if (r.get("view_count") or 0) > (best.get("view_count") or 0):
                    best = r

        video_id = best.get("id", "")
        url = best.get("url") or best.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"

        return {
            "url": url if url.startswith("http") else f"https://www.youtube.com/watch?v={video_id}",
            "title": best.get("title", ""),
            "views": str(best.get("view_count", "")),
            "duration": str(best.get("duration_string", best.get("duration", ""))),
            "author": best.get("uploader", best.get("channel", "")),
            "video_id": video_id,
        }
    except subprocess.TimeoutExpired:
        print("  ⚠ YouTube search timed out")
        return None
    except Exception as e:
        print(f"  ⚠ YouTube search error: {e}")
        return None


def query_pending_spotify_links() -> list[dict]:
    """Query Notion for pending podcast links that are Spotify URLs."""
    results = []
    has_more = True
    start_cursor = None

    while has_more:
        body = {
            "filter": {
                "and": [
                    {"property": "Status", "select": {"equals": "pending"}},
                    {"property": "Category", "select": {"equals": "podcast"}},
                ]
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
            url_obj = props.get("Link URL", {}).get("url", "")
            if url_obj and "spotify.com" in url_obj:
                name_parts = props.get("Name", {}).get("title", [])
                name = name_parts[0]["plain_text"] if name_parts else ""
                notes_parts = props.get("Notes", {}).get("rich_text", [])
                notes = notes_parts[0]["plain_text"] if notes_parts else ""
                results.append({
                    "page_id": page["id"],
                    "url": url_obj,
                    "name": name,
                    "notes": notes,
                })

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return results


def update_spotify_row(page_id: str, metadata: dict, yt_url: str, original_notes: str = "") -> bool:
    """Update the original Spotify row: set status=converted, enrich with metadata."""
    properties = {
        "Status": {"select": {"name": "converted"}},
    }

    # Update the Name from generic "open.spotify.com" to actual episode title
    if metadata.get("title"):
        properties["Name"] = {
            "title": [{"text": {"content": f"🟢 {metadata['title'][:195]}"}}]
        }
    if metadata.get("author"):
        properties["Author"] = {
            "rich_text": [{"text": {"content": metadata["author"][:200]}}]
        }
    if metadata.get("duration"):
        properties["Duration"] = {
            "rich_text": [{"text": {"content": metadata["duration"]}}]
        }
    if metadata.get("views"):
        properties["Source Views"] = {
            "rich_text": [{"text": {"content": metadata["views"]}}]
        }

    # Preserve original notes + append YouTube reference
    notes_parts = []
    if original_notes:
        notes_parts.append(original_notes)
    notes_parts.append(f"YouTube version: {yt_url}")
    properties["Notes"] = {
        "rich_text": [{"text": {"content": "\n".join(notes_parts)[:2000]}}]
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
        print(f"  ❌ Spotify row update failed: {resp.status_code} {resp.text[:200]}")
        return False


def create_youtube_row(yt_metadata: dict, spotify_url: str, original_notes: str) -> bool:
    """Create a new Links Queue row for the YouTube version."""
    title = yt_metadata.get("title", "YouTube podcast")

    properties = {
        "Name": {"title": [{"text": {"content": title[:200]}}]},
        "Link URL": {"url": yt_metadata["url"]},
        "Category": {"select": {"name": "podcast"}},
        "Timestamp": {"date": {"start": datetime.now().isoformat()[:10]}},
        "Status": {"select": {"name": "pending"}},
    }

    # Combine original notes with Spotify source reference
    notes_parts = []
    if original_notes:
        notes_parts.append(original_notes)
    notes_parts.append(f"Converted from Spotify: {spotify_url}")
    properties["Notes"] = {
        "rich_text": [{"text": {"content": "\n".join(notes_parts)[:2000]}}]
    }

    # Add metadata we already have
    if yt_metadata.get("author"):
        properties["Author"] = {
            "rich_text": [{"text": {"content": yt_metadata["author"][:200]}}]
        }
    if yt_metadata.get("duration"):
        properties["Duration"] = {
            "rich_text": [{"text": {"content": yt_metadata["duration"]}}]
        }
    if yt_metadata.get("views"):
        properties["Source Views"] = {
            "rich_text": [{"text": {"content": yt_metadata["views"]}}]
        }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json={"parent": {"database_id": NOTION_LINKS_DB_ID}, "properties": properties},
        timeout=10,
    )

    if resp.status_code == 200:
        return True
    else:
        print(f"  ❌ YouTube row creation failed: {resp.status_code} {resp.text[:200]}")
        return False


def process_spotify_link(page_id: str, spotify_url: str, name: str, notes: str) -> bool:
    """
    Full conversion flow:
    1. Get Spotify metadata (title, etc.)
    2. Search YouTube for matching episode
    3. Update Spotify row with metadata + status=converted
    4. Create new YouTube row with metadata + notes copied
    """
    # Step 1: Get Spotify episode info
    print(f"  🟢 Fetching Spotify metadata...")
    spotify_meta = get_spotify_metadata(spotify_url)
    episode_title = spotify_meta.get("title", "")

    if episode_title:
        print(f"  📝 Episode: {episode_title[:80]}")
    else:
        print(f"  ⚠ No title from Spotify oEmbed — using URL for search")
        episode_title = name if name != "open.spotify.com" else ""

    if not episode_title:
        print(f"  ❌ Cannot determine episode title — skipping")
        return False

    # Step 2: Search YouTube
    search_query = episode_title
    print(f"  🔍 Searching YouTube: {search_query[:60]}...")
    yt_result = search_youtube(search_query)

    if not yt_result:
        print(f"  ❌ No YouTube match found — leaving as pending")
        # Still update the Spotify row with metadata even if no YT match
        if spotify_meta.get("title") and page_id:
            properties = {
                "Name": {"title": [{"text": {"content": spotify_meta["title"][:200]}}]},
            }
            requests.patch(
                f"https://api.notion.com/v1/pages/{page_id}",
                headers=NOTION_HEADERS,
                json={"properties": properties},
                timeout=15,
            )
            print(f"  📝 Updated Spotify row with episode title at least")
        return False

    print(f"  🎬 Found: {yt_result['title'][:60]} | {yt_result.get('duration', '?')} | {yt_result.get('views', '?')} views")
    print(f"  🔗 {yt_result['url']}")

    # Step 3: Update original Spotify row → converted + metadata
    if page_id:
        ok = update_spotify_row(page_id, {
            "title": spotify_meta.get("title") or yt_result.get("title", ""),
            "author": yt_result.get("author", ""),
            "duration": yt_result.get("duration", ""),
            "views": yt_result.get("views", ""),
        }, yt_result["url"], notes)
        if ok:
            print(f"  ✅ Spotify row → converted (enriched with title + metadata)")

    # Step 4: Create new YouTube row with notes copied
    ok = create_youtube_row(yt_result, spotify_url, notes)
    if ok:
        print(f"  ✅ YouTube row created → pending (ready for transcript extraction)")

    return True


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if args:
        # Single URL mode
        url = args[0]
        print(f"🟢 Processing single Spotify URL: {url}")
        # Find in Notion
        body = {
            "filter": {"property": "Link URL", "url": {"equals": url}},
            "page_size": 1,
        }
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_LINKS_DB_ID}/query",
            headers=NOTION_HEADERS,
            json=body,
            timeout=15,
        )
        page_id = ""
        notes = ""
        name = ""
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                page_id = results[0]["id"]
                props = results[0]["properties"]
                name_parts = props.get("Name", {}).get("title", [])
                name = name_parts[0]["plain_text"] if name_parts else ""
                notes_parts = props.get("Notes", {}).get("rich_text", [])
                notes = notes_parts[0]["plain_text"] if notes_parts else ""
        process_spotify_link(page_id, url, name, notes)
    else:
        # Batch mode
        print("🔍 Querying Notion for pending Spotify podcast links...")
        links = query_pending_spotify_links()

        if not links:
            print("✅ No pending Spotify links to convert.")
            return

        print(f"📋 Found {len(links)} pending Spotify links\n")

        if dry_run:
            for i, link in enumerate(links, 1):
                print(f"  {i}. {link['name'][:50]} — {link['url'][:60]}")
            print(f"\nRun without --dry-run to process these.")
            return

        success = 0
        failed = 0
        for i, link in enumerate(links, 1):
            print(f"[{i}/{len(links)}] {link['name'][:50]} — {link['url'][:60]}")
            if process_spotify_link(link["page_id"], link["url"], link["name"], link["notes"]):
                success += 1
            else:
                failed += 1
            print()

        print(f"✅ Done: {success} converted, {failed} failed/skipped")


if __name__ == "__main__":
    main()
