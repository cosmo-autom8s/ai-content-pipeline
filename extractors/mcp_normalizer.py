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


def save_raw_output(output: str, prefix: str, batch_dir: Path | None = None) -> Path:
    """Save raw command output for an MCP batch."""
    target_dir = batch_dir or BACKUP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filepath = target_dir / f"{prefix}_{timestamp}.txt"
    filepath.write_text(output, encoding="utf-8")
    return filepath


def parse_extract_result_output(output: str, links: list[dict]) -> dict:
    """Parse the structured EXTRACT_RESULT line from an MCP worker response.

    Returns a normalized summary dict:
    {
      "extracted": int,
      "failed": int,
      "details": [{url, status, title, error}],
      "parsed": bool,
    }
    """
    default_details = [
        {
            "url": link.get("url", ""),
            "status": "unknown",
            "title": link.get("name", ""),
            "error": "missing EXTRACT_RESULT summary",
        }
        for link in links
    ]

    for line in reversed(output.splitlines()):
        if not line.startswith("EXTRACT_RESULT::"):
            continue
        try:
            summary = json.loads(line.removeprefix("EXTRACT_RESULT::"))
        except json.JSONDecodeError:
            break

        raw_details = summary.get("details", [])
        normalized_details = []
        for detail in raw_details:
            normalized_details.append({
                "url": detail.get("url", ""),
                "status": detail.get("status", "unknown"),
                "title": detail.get("title", detail.get("url", "")),
                "error": detail.get("error", ""),
            })

        extracted = summary.get("extracted")
        if not isinstance(extracted, int):
            extracted = sum(1 for item in normalized_details if item["status"] == "ok")
        failed = summary.get("failed")
        if not isinstance(failed, int):
            failed = sum(1 for item in normalized_details if item["status"] != "ok")

        return {
            "extracted": extracted,
            "failed": failed,
            "details": normalized_details,
            "parsed": True,
        }

    return {
        "extracted": 0,
        "failed": len(default_details),
        "details": default_details,
        "parsed": False,
    }
