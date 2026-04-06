#!/usr/bin/env python3
"""
Ideation Engine — Step 6 of Content Engine

Interactive script designed to run via Claude Code. Queries Notion for
links marked 'generate_ideas', formats the ideation prompt, and prints it
so Claude can generate content ideas. Ideas are then written back to Content Ideas DB.

Workflow: In Notion, set a link's status to 'generate_ideas' to queue it.
This script picks up only those pre-selected links.

Usage (run in Claude Code):
    python engines/ideation.py              # Pipeline mode: 4-skill ideation (default)
    python engines/ideation.py --list       # List queued links without processing
    python engines/ideation.py --id PAGE_ID # Process a specific link by Notion page ID
    python engines/ideation.py --legacy     # Legacy mode: single-shot prompt from ideation.txt
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_LINKS_DB_ID = os.getenv("NOTION_LINKS_DB_ID")
NOTION_IDEAS_DB_ID = os.getenv("NOTION_IDEAS_DB_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

PROMPT_TEMPLATE = (Path(__file__).parent.parent / "prompts" / "ideation.txt").read_text()
PIPELINE_PROMPT = (Path(__file__).parent.parent / "prompts" / "ideation_pipeline.md").read_text()
CREATOR_CONTEXT = (Path(__file__).parent.parent / "prompts" / "creator_context.md").read_text()


def _parse_json_arg(raw: str, label: str) -> dict | list:
    """Parse a JSON CLI argument with a clearer error message."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {exc}") from exc


def get_text_prop(props: dict, key: str) -> str:
    """Extract plain text from a Notion rich_text or title property."""
    prop = props.get(key, {})
    if prop.get("type") == "title":
        parts = prop.get("title", [])
    elif prop.get("type") == "rich_text":
        parts = prop.get("rich_text", [])
    else:
        return ""
    return parts[0]["plain_text"] if parts else ""


def get_select_prop(props: dict, key: str) -> str:
    """Extract select value from a Notion property."""
    prop = props.get(key, {})
    sel = prop.get("select")
    return sel["name"] if sel else ""


def query_generate_ideas_links() -> list[dict]:
    """Query Notion for links with status=generate_ideas."""
    results = []
    has_more = True
    start_cursor = None

    while has_more:
        body = {
            "filter": {
                "property": "Status",
                "select": {"equals": "generate_ideas"},
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
            results.append({
                "page_id": page["id"],
                "name": get_text_prop(props, "Name"),
                "url": props.get("Link URL", {}).get("url", ""),
                "category": get_select_prop(props, "Category"),
                "transcript": get_text_prop(props, "Transcript"),
                "notes": get_text_prop(props, "Notes"),
                "original_caption": get_text_prop(props, "Original Caption"),
                "views": get_text_prop(props, "Source Views"),
                "likes": get_text_prop(props, "Source Likes"),
            })

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return results


def get_link_by_id(page_id: str) -> dict | None:
    """Fetch a specific link by Notion page ID."""
    resp = requests.get(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"Error fetching page: {resp.status_code} {resp.text[:200]}")
        return None

    page = resp.json()
    props = page["properties"]
    return {
        "page_id": page["id"],
        "name": get_text_prop(props, "Name"),
        "url": props.get("Link URL", {}).get("url", ""),
        "category": get_select_prop(props, "Category"),
        "transcript": get_text_prop(props, "Transcript"),
        "notes": get_text_prop(props, "Notes"),
        "original_caption": get_text_prop(props, "Original Caption"),
        "views": get_text_prop(props, "Source Views"),
        "likes": get_text_prop(props, "Source Likes"),
    }


def format_prompt(link: dict) -> str:
    """Format the ideation prompt template with link data."""
    return PROMPT_TEMPLATE.format(
        source_url=link["url"],
        category=link["category"],
        views=link["views"] or "unknown",
        likes=link["likes"] or "unknown",
        original_caption=link.get("original_caption") or "(none)",
        transcript=link["transcript"] or "(no transcript available)",
        notes=link["notes"] or "(none)",
    )


def create_idea_in_notion(idea: dict, source_page_id: str, source_url: str = "") -> bool:
    """Write a content idea to the Content Ideas DB."""
    # Name = short punchy title; falls back to truncated description if no name provided
    idea_name = idea.get("name") or idea.get("description", "")[:200]
    properties = {
        "Name": {"title": [{"text": {"content": idea_name[:200]}}]},
        "Description": {"rich_text": [{"text": {"content": idea.get("description", "")[:2000]}}]},
        "Reasoning": {"rich_text": [{"text": {"content": idea.get("reasoning", "")[:2000]}}]},
        "Status": {"select": {"name": "new"}},
    }

    # Set hooks 1-5 (new pipeline format) or fall back to legacy suggested_hook
    for i in range(1, 6):
        hook_key = f"hook_{i}"
        hook_text = idea.get(hook_key, "")
        if hook_text:
            properties[f"Hook {i}"] = {
                "rich_text": [{"text": {"content": str(hook_text)[:2000]}}]
            }
    # Legacy fallback: if only suggested_hook exists (old format), put it in Hook 1
    if not idea.get("hook_1") and idea.get("suggested_hook"):
        properties["Hook 1"] = {
            "rich_text": [{"text": {"content": idea["suggested_hook"][:2000]}}]
        }

    if source_url:
        properties["Original URL"] = {"url": source_url}

    # Set angle if valid
    valid_angles = ["copy_it", "remix_it", "react_to_it", "tool_review", "freebie_inspiration"]
    if idea.get("angle") in valid_angles:
        properties["Angle"] = {"select": {"name": idea["angle"]}}

    # Set format if valid
    valid_formats = ["talking_head", "split_screen", "carousel"]
    if idea.get("format") in valid_formats:
        properties["Format"] = {"select": {"name": idea["format"]}}

    # Set urgency if valid
    valid_urgencies = ["newsworthy", "evergreen"]
    if idea.get("urgency") in valid_urgencies:
        properties["Urgency"] = {"select": {"name": idea["urgency"]}}

    # Set frame_type if valid (multi-select)
    valid_frames = ["pain", "prize", "news"]
    frame_types = idea.get("frame_type", [])
    if isinstance(frame_types, list):
        frames = [{"name": f} for f in frame_types if f in valid_frames]
        if frames:
            properties["Frame Type"] = {"multi_select": frames}

    # Set topic_cluster if provided
    if idea.get("topic_cluster"):
        properties["Topic Cluster"] = {
            "rich_text": [{"text": {"content": str(idea["topic_cluster"])[:2000]}}]
        }

    # Set score if provided (number 1-10 from creative director)
    if idea.get("score") is not None:
        try:
            properties["Score"] = {"number": float(idea["score"])}
        except (ValueError, TypeError):
            pass

    # Set top pick flag
    if idea.get("top_pick"):
        properties["Top Pick"] = {"checkbox": True}

    # Set filming setup if valid (multi-select)
    valid_setups = ["talking_head", "screen_recording", "walk_and_talk", "studio", "split_screen_react"]
    filming_setup = idea.get("filming_setup", [])
    if isinstance(filming_setup, str):
        filming_setup = [filming_setup]
    if isinstance(filming_setup, list):
        setups = [{"name": s} for s in filming_setup if s in valid_setups]
        if setups:
            properties["Filming Setup"] = {"multi_select": setups}

    # Set filming priority if valid
    valid_priorities = ["film_now", "film_soon", "batch_next", "shelved"]
    if idea.get("filming_priority") in valid_priorities:
        properties["Filming Priority"] = {"select": {"name": idea["filming_priority"]}}

    # Link to source
    if source_page_id:
        properties["Source Link"] = {
            "relation": [{"id": source_page_id}]
        }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json={"parent": {"database_id": NOTION_IDEAS_DB_ID}, "properties": properties},
        timeout=15,
    )

    if resp.status_code == 200:
        return True
    else:
        print(f"  Error creating idea: {resp.status_code} {resp.text[:200]}")
        return False


def mark_link_processed(page_id: str) -> bool:
    """Update a link's status to 'processed' after ideation."""
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json={"properties": {"Status": {"select": {"name": "processed"}}}},
        timeout=15,
    )
    return resp.status_code == 200


def save_ideas(ideas_json: str, source_page_id: str, source_url: str = "") -> int:
    """Parse JSON ideas and save them to Notion. Returns count saved."""
    try:
        ideas = json.loads(ideas_json)
        if not isinstance(ideas, list):
            ideas = [ideas]
    except json.JSONDecodeError as e:
        print(f"Error parsing ideas JSON: {e}")
        return 0

    saved = 0
    for idea in ideas:
        if create_idea_in_notion(idea, source_page_id, source_url):
            saved += 1
            print(f"  Saved: {idea.get('angle', '?')} — {idea.get('description', '')[:60]}")

    if saved > 0:
        mark_link_processed(source_page_id)

    return saved


def format_pipeline_source(link: dict) -> str:
    """Format link data as structured source material for the pipeline prompt."""
    caption = link.get("original_caption") or "(none)"
    transcript = link["transcript"] or "(no transcript available)"
    notes = link["notes"] or "(none)"
    lines = [
        f"Source URL: {link['url']}",
        f"Category: {link['category']}",
        f"Views: {link['views'] or 'unknown'} | Likes: {link['likes'] or 'unknown'}",
        f"Original Caption: {caption}",
        f"Transcript:\n{transcript}",
        f"Creator's Notes: {notes}",
        f"Page ID: {link['page_id']}",
    ]
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    use_legacy = "--legacy" in args

    if "--save" in args:
        idx = args.index("--save")
        if idx + 2 >= len(args):
            print("Usage: python engines/ideation.py --save '{\"page_id\":\"...\",\"url\":\"...\"}' '[...]'")
            return

        try:
            source = _parse_json_arg(args[idx + 1], "source")
            ideas = _parse_json_arg(args[idx + 2], "ideas")
        except ValueError as exc:
            print(exc)
            return

        if not isinstance(source, dict):
            print("Source JSON must be an object with at least page_id.")
            return
        page_id = source.get("page_id", "")
        source_url = source.get("url", "")
        if not page_id:
            print("Source JSON is missing page_id.")
            return

        ideas_json = json.dumps(ideas)
        saved = save_ideas(ideas_json, page_id, source_url)
        print(f"\n✅ Done: {saved} idea(s) saved")
        return

    if "--list" in args:
        print("Querying links marked 'generate_ideas'...")
        links = query_generate_ideas_links()
        if not links:
            print("No links queued for ideation.")
            return
        print(f"\n{len(links)} link(s) queued for ideation:\n")
        for i, link in enumerate(links, 1):
            transcript_len = len(link["transcript"].split()) if link["transcript"] else 0
            print(f"  {i}. [{link['category']}] {link['name'][:60]}")
            print(f"     URL: {link['url'][:80]}")
            print(f"     Transcript: {transcript_len} words")
            if link["notes"]:
                print(f"     Notes: {link['notes'][:80]}")
            print(f"     Page ID: {link['page_id']}")
            print()
        return

    if "--id" in args:
        idx = args.index("--id")
        if idx + 1 >= len(args):
            print("Usage: --id PAGE_ID")
            return
        page_id = args[idx + 1]
        link = get_link_by_id(page_id)
        if not link:
            return
        links = [link]
    else:
        print("Querying links marked 'generate_ideas'...")
        links = query_generate_ideas_links()

    if not links:
        print("No links queued for ideation.")
        return

    print(f"\n{len(links)} link(s) ready for ideation.\n")

    if use_legacy:
        # Legacy mode: single-shot prompt from ideation.txt
        print("(Legacy mode — using ideation.txt prompt)\n")
        print("=" * 80)
        for i, link in enumerate(links, 1):
            print(f"\n--- Link {i}/{len(links)}: {link['name'][:60]} ---")
            print(f"Page ID: {link['page_id']}")
            print()
            print(format_prompt(link))
            print("=" * 80)
    else:
        # Pipeline mode: structured output for 4-skill pipeline
        print("=" * 80)
        print("IDEATION PIPELINE — Quick Mode")
        print("=" * 80)
        print()
        print("INSTRUCTIONS:")
        print(PIPELINE_PROMPT)
        print()
        print("CREATOR CONTEXT:")
        print(CREATOR_CONTEXT)
        print()
        print("=" * 80)
        print(f"SOURCE VIDEOS ({len(links)} links)")
        print("=" * 80)

        for i, link in enumerate(links, 1):
            print(f"\n--- Source {i}/{len(links)}: {link['name'][:60]} ---")
            print(format_pipeline_source(link))
            print()

        print("=" * 80)
        print()
        print("Run the 4-step pipeline above, then save results with:")
        for link in links:
            print(f'  python engines/ideation.py --save \'{{"page_id": "{link["page_id"]}", "url": "{link["url"]}"}}\' \'[...ideas json...]\'')
        print()


if __name__ == "__main__":
    main()
