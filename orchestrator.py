#!/usr/bin/env python3
"""
Evening Orchestrator — Step 7 of Content Engine

Runs the full evening pipeline:
1. Process any CSV exports in csv_inbox/
2. Query Links Queue for status=pending
3. Process YouTube links through transcript extractor
4. Extract short-form links (TikTok/Instagram/YT Shorts) via Claude CLI + TokScript MCP
5. Classify all newly transcribed links

Usage:
    python orchestrator.py              # Run full pipeline
    python orchestrator.py --dry-run    # Show what would be processed
    python orchestrator.py --status     # Show pipeline status overview
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from extractors.youtube import (
    extract_video_id,
    process_links_via_mcp,
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

# Categories — all video types now go through TokScript MCP via Claude CLI
AUTO_CATEGORIES = {"podcast", "long_form"}  # YouTube links — extracted via TokScript MCP
MANUAL_CATEGORIES = {"short_form", "tiktok", "reels", "yt_shorts"}  # extracted via TokScript MCP
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


MCP_EXTRACT_BUDGET = 0.50  # safety cap per orchestrator run
MCP_BACKUP_DIR = Path(__file__).parent / "csv_inbox" / "mcp_extracts"

# Claude CLI path — resolve once at import time
CLAUDE_CLI = shutil.which("claude")


def build_mcp_prompt(links: list[dict]) -> str:
    """Build the prompt sent to claude CLI for MCP transcript extraction."""
    urls_block = "\n".join(
        f"- page_id: {l['page_id']} | url: {l['url']} | name: {l['name'][:60]}"
        for l in links
    )
    return f"""You are a transcript extraction worker. Extract transcripts for the following links using TokScript MCP tools, then update each Notion page.

## Links to process
{urls_block}

## Instructions
For each link:
1. Detect platform from the URL (instagram, tiktok, or youtube).
2. Call the matching MCP tool to get the transcript:
   - Instagram: mcp__claude_ai_Tokscript__get_instagram_transcript (video_url, format: "json")
   - TikTok: mcp__claude_ai_Tokscript__get_tiktok_transcript (video_url, format: "json")
   - YouTube: mcp__claude_ai_Tokscript__get_youtube_transcript (video_url, format: "json")
3. Update the Notion page (use the page_id) via mcp__claude_ai_Notion__notion-update-page:
   - Set Status to "transcribed"
   - Set Transcript to all transcript segment texts joined with spaces (send the FULL transcript, do NOT truncate)
   - Set Name to first 60 chars of the title (break at word boundary)
   - Set "Original Caption" to the full title (send full text, do NOT truncate)
   - Set "Source Views" to the view count as a string
   - Set Duration to the duration as a string like "64.9s"
   - Set Author to the author username

Process all links. Call multiple MCP tools in parallel where possible.

After processing all links, output a JSON summary as the LAST line of your response, in this exact format:
EXTRACT_RESULT::{{"extracted": N, "failed": N, "details": [{{"url": "...", "status": "ok"|"error", "title": "...", "error": "..."}}]}}
"""


MCP_BATCH_SIZE = 10  # links per Claude CLI call


def _run_mcp_batch(links: list[dict]) -> int:
    """Run a single MCP extraction batch via Claude CLI. Returns number extracted."""
    prompt = build_mcp_prompt(links)

    cmd = [
        CLAUDE_CLI,
        "-p", prompt,
        "--model", "sonnet",
        "--output-format", "text",
        "--max-budget-usd", str(MCP_EXTRACT_BUDGET),
        "--permission-mode", "bypassPermissions",
        "--allowedTools",
        "mcp__claude_ai_Tokscript__get_instagram_transcript",
        "mcp__claude_ai_Tokscript__get_tiktok_transcript",
        "mcp__claude_ai_Tokscript__get_youtube_transcript",
        "mcp__claude_ai_Tokscript__get_bulk_transcripts",
        "mcp__claude_ai_Notion__notion-update-page",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes per batch (~30s per link for MCP + Notion update)
            cwd=str(Path(__file__).parent),
        )
    except subprocess.TimeoutExpired:
        print("    Batch timed out after 10 minutes")
        return 0

    if result.returncode != 0:
        print(f"    Claude CLI exited with code {result.returncode}")
        if result.stderr:
            print(f"    stderr: {result.stderr[:300]}")
        return 0

    output = result.stdout

    # Save backup
    MCP_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = MCP_BACKUP_DIR / f"mcp_extract_{timestamp}.txt"
    backup_path.write_text(output, encoding="utf-8")

    # Parse result summary
    extracted = 0
    for line in reversed(output.splitlines()):
        if line.startswith("EXTRACT_RESULT::"):
            try:
                summary = json.loads(line.removeprefix("EXTRACT_RESULT::"))
                extracted = summary.get("extracted", 0)
                failed = summary.get("failed", 0)
                details = summary.get("details", [])

                for d in details:
                    status_icon = "ok" if d["status"] == "ok" else "FAIL"
                    title = d.get("title", d.get("url", ""))[:50]
                    msg = f"    [{status_icon}] {title}"
                    if d.get("error"):
                        msg += f" — {d['error']}"
                    print(msg)

                if failed:
                    print(f"    {failed} link(s) failed — check backup: {backup_path}")
            except json.JSONDecodeError:
                print("    Could not parse extraction result summary")
            break
    else:
        extracted = output.count("transcribed")
        if extracted:
            print(f"    Batch completed (estimated {extracted} updates)")
        else:
            print("    Batch completed but could not verify results")

    return extracted


def extract_shortform_via_mcp(links: list[dict], dry_run: bool = False) -> int:
    """Extract transcripts for short-form links by shelling out to claude CLI with MCP tools.

    Processes links in batches of MCP_BATCH_SIZE to avoid timeouts and respect TokScript rate limits.
    Returns the number of successfully extracted links.
    """
    if not links:
        return 0

    if not CLAUDE_CLI:
        print("  claude CLI not found in PATH — skipping MCP extraction")
        print("  Fallback: Export CSV from TokScript web → csv_inbox/")
        return 0

    if dry_run:
        print(f"  (dry run — would extract {len(links)} link(s) via MCP)")
        return 0

    total_extracted = 0
    batches = [links[i:i + MCP_BATCH_SIZE] for i in range(0, len(links), MCP_BATCH_SIZE)]

    print(f"  Extracting {len(links)} link(s) via Claude CLI + TokScript MCP ({len(batches)} batch(es) of {MCP_BATCH_SIZE})...")

    for batch_num, batch in enumerate(batches, 1):
        print(f"\n  Batch {batch_num}/{len(batches)} ({len(batch)} links):")
        extracted = _run_mcp_batch(batch)
        total_extracted += extracted
        print(f"    Batch result: {extracted}/{len(batch)} extracted")

    return total_extracted


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
        print(f"  Short-form (MCP extract): {len(manual_links)}")
        print(f"  Skipped (no extractor): {len(skipped_links)}")
        print()

        # Step 3: Process YouTube links via TokScript MCP
        if youtube_links:
            print(f"Processing {len(youtube_links)} YouTube link(s) via MCP...")
            yt_success = process_links_via_mcp(youtube_links, dry_run)
            if not dry_run:
                print(f"YouTube extraction: {yt_success}/{len(youtube_links)} successful")
            print()

        # Step 4: Extract short-form links via Claude CLI + TokScript MCP
        if manual_links:
            print(f"Processing {len(manual_links)} short-form link(s) via MCP...")
            mcp_success = extract_shortform_via_mcp(manual_links, dry_run)
            if not dry_run:
                print(f"MCP extraction: {mcp_success}/{len(manual_links)} successful")
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
