#!/usr/bin/env python3
"""
Caption Generator — Step 8 of Content Engine

Interactive script designed to run via Claude Code. Queries Content Ideas DB
for ideas with status=filmed, formats the caption prompt, and prints it so
Claude can generate platform-specific captions. Captions are written back
to the Content Ideas DB.

Usage (run in Claude Code):
    python engines/captions.py              # Process all filmed ideas
    python engines/captions.py --list       # List filmed ideas
    python engines/captions.py --id PAGE_ID # Process a specific idea
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
NOTION_IDEAS_DB_ID = os.getenv("NOTION_IDEAS_DB_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

PROMPT_TEMPLATE = (Path(__file__).parent.parent / "prompts" / "captions.txt").read_text()


def _parse_json_arg(raw: str) -> dict:
    """Parse JSON passed on the CLI."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid captions JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Captions JSON must be an object.")
    return data


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


def query_filmed_ideas() -> list[dict]:
    """Query Content Ideas DB for ideas with status=filmed."""
    results = []
    has_more = True
    start_cursor = None

    while has_more:
        body = {
            "filter": {
                "property": "Status",
                "select": {"equals": "filmed"},
            },
            "page_size": 100,
        }
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_IDEAS_DB_ID}/query",
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
            hooks = [
                get_text_prop(props, "Hook 1"),
                get_text_prop(props, "Hook 2"),
                get_text_prop(props, "Hook 3"),
                get_text_prop(props, "Hook 4"),
                get_text_prop(props, "Hook 5"),
            ]
            results.append({
                "page_id": page["id"],
                "name": get_text_prop(props, "Name"),
                "description": get_text_prop(props, "Description"),
                "hook": next((hook for hook in hooks if hook), ""),
                "format": get_select_prop(props, "Format"),
                "angle": get_select_prop(props, "Angle"),
            })

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return results


def get_idea_by_id(page_id: str) -> dict | None:
    """Fetch a specific idea by Notion page ID."""
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
    hooks = [
        get_text_prop(props, "Hook 1"),
        get_text_prop(props, "Hook 2"),
        get_text_prop(props, "Hook 3"),
        get_text_prop(props, "Hook 4"),
        get_text_prop(props, "Hook 5"),
    ]
    return {
        "page_id": page["id"],
        "name": get_text_prop(props, "Name"),
        "description": get_text_prop(props, "Description"),
        "hook": next((hook for hook in hooks if hook), ""),
        "format": get_select_prop(props, "Format"),
        "angle": get_select_prop(props, "Angle"),
    }


def format_prompt(idea: dict) -> str:
    """Format the caption prompt template with idea data."""
    return PROMPT_TEMPLATE.format(
        idea_description=idea["description"] or idea["name"],
        suggested_hook=idea["hook"] or "(no hook provided)",
        format=idea["format"] or "talking_head",
    )


def save_captions(page_id: str, captions_json: str) -> bool:
    """Parse JSON captions and update the Content Ideas page."""
    try:
        captions = json.loads(captions_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing captions JSON: {e}")
        return False

    properties = {
        "Status": {"select": {"name": "captioned"}},
    }

    platform_fields = {
        "caption_tiktok": "Caption TikTok",
        "caption_instagram": "Caption Instagram",
        "caption_youtube": "Caption YouTube",
        "caption_linkedin": "Caption LinkedIn",
    }

    for json_key, notion_key in platform_fields.items():
        text = captions.get(json_key, "")
        if text:
            properties[notion_key] = {
                "rich_text": [{"text": {"content": text[:2000]}}]
            }

    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json={"properties": properties},
        timeout=15,
    )

    if resp.status_code == 200:
        print(f"  Captions saved, status → captioned")
        return True
    else:
        print(f"  Error saving captions: {resp.status_code} {resp.text[:200]}")
        return False


def main():
    args = sys.argv[1:]

    if "--save" in args:
        idx = args.index("--save")
        if idx + 2 >= len(args):
            print("Usage: python engines/captions.py --save PAGE_ID '{\"caption_tiktok\":\"...\"}'")
            return
        page_id = args[idx + 1]
        try:
            captions = _parse_json_arg(args[idx + 2])
        except ValueError as exc:
            print(exc)
            return
        save_captions(page_id, json.dumps(captions))
        return

    if "--list" in args:
        print("Querying filmed ideas...")
        ideas = query_filmed_ideas()
        if not ideas:
            print("No filmed ideas found.")
            return
        print(f"\n{len(ideas)} filmed idea(s):\n")
        for i, idea in enumerate(ideas, 1):
            print(f"  {i}. [{idea['angle']}] {idea['name'][:60]}")
            print(f"     Hook: {idea['hook'][:80]}")
            print(f"     Format: {idea['format']}")
            print(f"     Page ID: {idea['page_id']}")
            print()
        return

    if "--id" in args:
        idx = args.index("--id")
        if idx + 1 >= len(args):
            print("Usage: --id PAGE_ID")
            return
        page_id = args[idx + 1]
        idea = get_idea_by_id(page_id)
        if not idea:
            return
        ideas = [idea]
    else:
        print("Querying filmed ideas...")
        ideas = query_filmed_ideas()

    if not ideas:
        print("No filmed ideas to process.")
        return

    print(f"\n{len(ideas)} idea(s) ready for captions.\n")
    print("=" * 80)

    for i, idea in enumerate(ideas, 1):
        print(f"\n--- Idea {i}/{len(ideas)}: {idea['name'][:60]} ---")
        print(f"Angle: {idea['angle']}")
        print(f"Hook: {idea['hook']}")
        print(f"Format: {idea['format']}")
        print(f"Page ID: {idea['page_id']}")
        print()
        print("PROMPT:")
        print("=" * 80)
        print(format_prompt(idea))
        print("=" * 80)
        print()
        print(">>> Run this via Claude Code to generate captions directly.")
        print()

        if i < len(ideas):
            print("--- Next idea follows ---")


if __name__ == "__main__":
    main()
