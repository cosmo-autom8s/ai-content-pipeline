#!/usr/bin/env python3
"""
MCP Normalizer — Converts TokScript MCP responses to the row dict
shape expected by tokscript_parser.update_notion_page() / create_notion_page().

Also provides platform detection from URLs.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

# Platform detection patterns (from bot/main.py URL_RULES)
PLATFORM_PATTERNS = [
    (re.compile(r"tiktok\.com|vm\.tiktok\.com"), "tiktok"),
    (re.compile(r"instagram\.com/(reel|reels)/"), "instagram"),
    (re.compile(r"youtube\.com/shorts/"), "youtube"),
    (re.compile(r"youtube\.com/watch"), "youtube"),
    (re.compile(r"youtu\.be/"), "youtube"),
]

BACKUP_DIR = Path(__file__).parent.parent / "csv_inbox" / "mcp_extracts"


def detect_platform(url: str) -> str | None:
    """Detect platform from a URL. Returns 'instagram', 'tiktok', 'youtube', or None."""
    for pattern, platform in PLATFORM_PATTERNS:
        if pattern.search(url):
            return platform
    return None


def normalize_mcp_response(mcp_data: dict, url: str) -> dict:
    """Convert MCP transcript response to the row dict shape expected by tokscript_parser.

    Returns a dict with keys: URL, Title, Transcript, Views, Duration, Author, Platform
    """
    # Join transcript segments into flat text
    transcript = ""
    t = mcp_data.get("transcript", {})
    if isinstance(t, dict):
        segments = t.get("segments", [])
        transcript = " ".join(seg.get("text", "") for seg in segments)
    elif isinstance(t, str):
        transcript = t

    # Extract fields
    author_data = mcp_data.get("author", {})
    author = author_data.get("username", "") if isinstance(author_data, dict) else str(author_data)

    views = mcp_data.get("views", "")
    if isinstance(views, (int, float)):
        views = str(int(views))

    duration = mcp_data.get("duration", "")
    if isinstance(duration, (int, float)):
        duration = f"{duration}s"

    platform = detect_platform(url) or "unknown"

    return {
        "URL": url,
        "Title": mcp_data.get("title", ""),
        "Transcript": transcript,
        "Views": str(views),
        "Duration": str(duration),
        "Author": author,
        "Platform": platform,
    }


def save_backup(results: list[dict], batch_dir: Path | None = None) -> Path:
    """Save a JSON backup of extracted MCP results.

    Returns the path to the saved file.
    """
    target_dir = batch_dir or BACKUP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filepath = target_dir / f"mcp_extract_{timestamp}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return filepath
