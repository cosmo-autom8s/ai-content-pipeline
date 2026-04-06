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

import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from extractors.youtube import (
    extract_video_id,
    process_links_via_mcp,
)
from extractors.spotify_to_youtube import query_pending_spotify_links, process_spotify_link
from extractors.mcp_normalizer import parse_extract_result_output, save_backup, save_raw_output
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


def print_stage_result(name: str, planned: int, completed: int | None = None, note: str = "") -> str:
    """Return a consistently formatted stage result string."""
    if completed is None:
        message = f"{name}: planned {planned}"
    else:
        message = f"{name}: {completed}/{planned} completed"
    if note:
        message += f" ({note})"
    return message


def route_pending_links(links: list[dict]) -> tuple[list[dict], list[dict], dict[str, list[dict]]]:
    """Split pending links into extraction buckets and grouped skip reasons."""
    youtube_links: list[dict] = []
    shortform_links: list[dict] = []
    skipped: dict[str, list[dict]] = {
        "non_extractable_category": [],
        "spotify_pending_conversion": [],
        "unknown": [],
    }

    for link in links:
        cat = link["category"]
        url = link["url"]
        has_yt = extract_video_id(url) is not None
        is_spotify = "spotify.com" in (url or "")

        if is_spotify:
            skipped["spotify_pending_conversion"].append(link)
        elif has_yt and cat in AUTO_CATEGORIES:
            youtube_links.append(link)
        elif cat in MANUAL_CATEGORIES:
            shortform_links.append(link)
        elif has_yt:
            youtube_links.append(link)
        elif cat in SKIP_CATEGORIES:
            skipped["non_extractable_category"].append(link)
        else:
            skipped["unknown"].append(link)

    return youtube_links, shortform_links, skipped


def print_skipped_links(skipped: dict[str, list[dict]]) -> None:
    """Print skipped links grouped by reason."""
    labels = {
        "non_extractable_category": "no extractor for category",
        "spotify_pending_conversion": "Spotify URL still pending conversion",
        "unknown": "unrecognized routing",
    }
    total = sum(len(items) for items in skipped.values())
    if not total:
        return

    print(f"Skipped links: {total}")
    for reason, items in skipped.items():
        if not items:
            continue
        print(f"  {labels[reason]}: {len(items)}")
        for link in items[:5]:
            print(f"    [{link['category']}] {link['name'][:50]} — {link['url'][:60]}")
        if len(items) > 5:
            print(f"    ... and {len(items) - 5} more")
    print()


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


def count_statuses(db_id: str) -> dict[str, int]:
    """Count all status values in a database in one paginated pass."""
    counts: dict[str, int] = {}
    has_more = True
    start_cursor = None

    while has_more:
        body: dict = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=NOTION_HEADERS,
            json=body,
            timeout=15,
        )
        if resp.status_code != 200:
            return {}

        data = resp.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            status_obj = props.get("Status", {}).get("select")
            status = status_obj["name"] if status_obj else "unknown"
            counts[status] = counts.get(status, 0) + 1

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return counts


def show_status():
    """Show pipeline status overview."""
    print("Pipeline Status Overview")
    print("=" * 50)
    links_counts = count_statuses(NOTION_LINKS_DB_ID)
    ideas_counts = count_statuses(NOTION_IDEAS_DB_ID)

    print("\nLinks Queue:")
    for status in [
        "pending",
        "transcribed",
        "classified",
        "classification_error",
        "generate_ideas",
        "processed",
        "converted",
        "archived",
    ]:
        count = links_counts.get(status, 0)
        print(f"  {status}: {count}")

    print("\nContent Ideas:")
    for status in ["new", "queued", "filming_today", "filmed", "captioned", "posted", "archived"]:
        print(f"  {status}: {ideas_counts.get(status, 0)}")

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

    raw_backup_path = save_raw_output(output, "mcp_extract", MCP_BACKUP_DIR)
    summary = parse_extract_result_output(output, links)
    json_backup_path = save_backup(
        [{
            "kind": "shortform_extract",
            "links": links,
            "summary": summary,
            "raw_output_path": str(raw_backup_path),
        }],
        MCP_BACKUP_DIR,
    )

    for detail in summary["details"]:
        status_icon = "ok" if detail["status"] == "ok" else "FAIL"
        title = detail.get("title", detail.get("url", ""))[:50]
        msg = f"    [{status_icon}] {title}"
        if detail.get("error"):
            msg += f" — {detail['error']}"
        print(msg)

    if not summary["parsed"]:
        print("    Could not parse extraction result summary — marked batch as failed in structured backup")
    elif summary["failed"]:
        print(f"    {summary['failed']} link(s) failed — check backup: {json_backup_path}")

    print(f"    Raw backup saved: {raw_backup_path}")
    print(f"    Structured backup saved: {json_backup_path}")
    return summary["extracted"]


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
    stage_results: list[str] = []

    # Step 1: Check for CSVs in inbox
    csv_files = list(CSV_INBOX.glob("*.csv")) if CSV_INBOX.exists() else []
    if csv_files:
        print(f"CSV Inbox: {len(csv_files)} TokScript export(s) found")
        processed_csvs = 0
        if not dry_run:
            from extractors.tokscript_parser import process_csv, PROCESSED_DIR
            for csv_path in csv_files:
                processed, skipped = process_csv(csv_path)
                if processed > 0:
                    PROCESSED_DIR.mkdir(exist_ok=True)
                    dest = PROCESSED_DIR / csv_path.name
                    csv_path.rename(dest)
                    print(f"  Moved to csv_inbox/processed/")
                    processed_csvs += 1
        else:
            for f in csv_files:
                print(f"  Would process: {f.name}")
        stage_results.append(
            print_stage_result(
                "CSV ingest",
                len(csv_files),
                None if dry_run else processed_csvs,
                "dry run" if dry_run else "",
            )
        )
        print()
    else:
        stage_results.append("CSV ingest: 0 file(s)")

    # Step 2: Convert pending Spotify podcast links
    spotify_links = query_pending_spotify_links()
    if spotify_links:
        print(f"Found {len(spotify_links)} pending Spotify podcast link(s)")
        if dry_run:
            for link in spotify_links[:10]:
                print(f"  Would convert: {link['name'][:50]} — {link['url'][:60]}")
            if len(spotify_links) > 10:
                print(f"  ... and {len(spotify_links) - 10} more")
        else:
            converted = 0
            for i, link in enumerate(spotify_links, 1):
                print(f"  [{i}/{len(spotify_links)}] Converting Spotify link...")
                if process_spotify_link(link["page_id"], link["url"], link["name"], link["notes"]):
                    converted += 1
                print()
            print(f"Spotify conversion: {converted}/{len(spotify_links)} successful")
        stage_results.append(
            print_stage_result(
                "Spotify conversion",
                len(spotify_links),
                None if dry_run else converted,
                "dry run" if dry_run else "",
            )
        )
        print()
    else:
        stage_results.append("Spotify conversion: 0 link(s)")

    # Step 3: Query pending links
    print("Querying pending links...")
    pending = query_all_pending()
    stage_results.append(f"Pending queue after setup stages: {len(pending)} link(s)")

    if not pending:
        print("No pending links.\n")
    else:
        youtube_links, manual_links, skipped_links = route_pending_links(pending)
        skipped_total = sum(len(items) for items in skipped_links.values())

        print(f"\nFound {len(pending)} pending links:")
        print(f"  YouTube (auto-extract): {len(youtube_links)}")
        print(f"  Short-form (MCP extract): {len(manual_links)}")
        print(f"  Skipped: {skipped_total}")
        print()

        # Step 4: Process YouTube links via TokScript MCP
        if youtube_links:
            print(f"Processing {len(youtube_links)} YouTube link(s) via MCP...")
            yt_success = process_links_via_mcp(youtube_links, dry_run)
            if not dry_run:
                print(f"YouTube extraction: {yt_success}/{len(youtube_links)} successful")
            stage_results.append(
                print_stage_result(
                    "YouTube extraction",
                    len(youtube_links),
                    None if dry_run else yt_success,
                    "dry run" if dry_run else "",
                )
            )
            print()
        else:
            stage_results.append("YouTube extraction: 0 link(s)")

        # Step 5: Extract short-form links via Claude CLI + TokScript MCP
        if manual_links:
            print(f"Processing {len(manual_links)} short-form link(s) via MCP...")
            mcp_success = extract_shortform_via_mcp(manual_links, dry_run)
            if not dry_run:
                print(f"MCP extraction: {mcp_success}/{len(manual_links)} successful")
            stage_results.append(
                print_stage_result(
                    "Short-form extraction",
                    len(manual_links),
                    None if dry_run else mcp_success,
                    "dry run" if dry_run else "",
                )
            )
            print()
        else:
            stage_results.append("Short-form extraction: 0 link(s)")

        print_skipped_links(skipped_links)
        stage_results.append(f"Skipped links: {skipped_total}")

    # Step 6: Classify newly transcribed links
    print("=" * 50)
    print("Classifying transcribed links...")
    if not dry_run:
        classified_count = classify_all_transcribed()
        print(f"\nClassification: {classified_count} links classified")
        stage_results.append(f"Classification: {classified_count} link(s) classified")
    else:
        classified_count = classify_all_transcribed(dry_run=True)
        print(f"\nClassification: {classified_count} links would be classified")
        stage_results.append(f"Classification: planned {classified_count} link(s)")
    print()

    # Step 7: Summary
    print("=" * 50)
    print("Run summary:")
    for line in stage_results:
        print(f"  - {line}")
    print()
    print("Next steps:")
    print("  1. Review classified links in Notion 'Classified' view")
    print("  2. Tag links for ideation: python engines/ideation.py --list")
    print("  3. Generate ideas: /ca-ideate")
    print("  4. Review Morning Menu in Notion")
    print()


if __name__ == "__main__":
    main()
