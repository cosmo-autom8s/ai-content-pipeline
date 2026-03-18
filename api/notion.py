"""Notion API client for Content Ideas DB.

Async client using httpx that queries the Content Ideas database and
parses Notion properties into clean Python dicts.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env from project root (same pattern as engines/ideation.py)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_IDEAS_DB_ID = os.getenv("NOTION_IDEAS_DB_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

NOTION_API_BASE = "https://api.notion.com/v1"


# ---------------------------------------------------------------------------
# Property extraction helpers
# ---------------------------------------------------------------------------

def _get_text(props: dict, key: str) -> str:
    """Extract plain text from a Notion rich_text or title property."""
    prop = props.get(key, {})
    if prop.get("type") == "title":
        parts = prop.get("title", [])
    elif prop.get("type") == "rich_text":
        parts = prop.get("rich_text", [])
    else:
        return ""
    return "".join(p["plain_text"] for p in parts) if parts else ""


def _get_select(props: dict, key: str) -> str | None:
    """Extract select value from a Notion property."""
    prop = props.get(key, {})
    sel = prop.get("select")
    return sel["name"] if sel else None


def _get_status(props: dict, key: str) -> str | None:
    """Extract status value from a Notion status property.

    Notion's 'status' type returns {"status": {"name": "..."}},
    which is different from select.
    """
    prop = props.get(key, {})
    status = prop.get("status")
    return status["name"] if status else None


def _get_multi_select(props: dict, key: str) -> list[str]:
    """Extract multi_select values as a list of strings."""
    prop = props.get(key, {})
    items = prop.get("multi_select", [])
    return [item["name"] for item in items]


def _get_number(props: dict, key: str) -> float | None:
    """Extract number value."""
    prop = props.get(key, {})
    return prop.get("number")


def _get_checkbox(props: dict, key: str) -> bool:
    """Extract checkbox value."""
    prop = props.get(key, {})
    return prop.get("checkbox", False)


def _get_url(props: dict, key: str) -> str | None:
    """Extract url value."""
    prop = props.get(key, {})
    return prop.get("url")


def _get_date(props: dict, key: str) -> str | None:
    """Extract date as ISO string."""
    prop = props.get(key, {})
    date = prop.get("date")
    if date:
        return date.get("start")
    return None


def _get_relation(props: dict, key: str) -> list[str]:
    """Extract relation as list of page IDs."""
    prop = props.get(key, {})
    items = prop.get("relation", [])
    return [item["id"] for item in items]


def _parse_post_urls(text: str) -> list[str]:
    """Split newline-separated text into list of URL strings."""
    if not text:
        return []
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Idea parsers
# ---------------------------------------------------------------------------

def _parse_idea_list(page: dict) -> dict:
    """Parse a Notion page into a list-level idea dict."""
    props = page["properties"]
    return {
        "id": page["id"],
        "name": _get_text(props, "Name"),
        "score": _get_number(props, "Score"),
        "top_pick": _get_checkbox(props, "Top Pick"),
        "status": _get_status(props, "Status"),
        "main_topic": _get_text(props, "Main Topic"),
        "format": _get_select(props, "Format"),
        "filming_setup": _get_multi_select(props, "Filming Setup"),
        "filming_priority": _get_select(props, "Filming Priority"),
        "frame_type": _get_multi_select(props, "Frame Type"),
        "topic_cluster": _get_text(props, "Topic Cluster"),
        "urgency": _get_select(props, "Urgency"),
        "description": _get_text(props, "Description"),
    }


async def _resolve_source_link(client: httpx.AsyncClient, page_ids: list[str]) -> dict | None:
    """Resolve a Source Link relation to {name, url}."""
    if not page_ids:
        return None
    page_id = page_ids[0]
    resp = await client.get(
        f"{NOTION_API_BASE}/pages/{page_id}",
        headers=NOTION_HEADERS,
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    props = data["properties"]
    name = _get_text(props, "Name")
    # Construct Notion URL: https://notion.so/{page_id_without_hyphens}
    clean_id = page_id.replace("-", "")
    return {"name": name, "url": f"https://notion.so/{clean_id}"}


def _parse_idea_detail(page: dict) -> dict:
    """Parse a Notion page into a full detail idea dict (without source_link resolution)."""
    props = page["properties"]
    idea = _parse_idea_list(page)
    idea.update({
        "angle": _get_select(props, "Angle"),
        "reasoning": _get_text(props, "Reasoning"),
        "hook_1": _get_text(props, "Hook 1"),
        "hook_2": _get_text(props, "Hook 2"),
        "hook_3": _get_text(props, "Hook 3"),
        "hook_4": _get_text(props, "Hook 4"),
        "hook_5": _get_text(props, "Hook 5"),
        "original_url": _get_url(props, "Original URL"),
        "source_link_ids": _get_relation(props, "Source Link"),
        "filmed_date": _get_date(props, "filmed_date"),
        "posted_date": _get_date(props, "posted_date"),
        "caption_tiktok": _get_text(props, "caption_tiktok"),
        "caption_instagram": _get_text(props, "caption_instagram"),
        "caption_youtube": _get_text(props, "caption_youtube"),
        "caption_linkedin": _get_text(props, "caption_linkedin"),
        "post_urls": _parse_post_urls(_get_text(props, "post URLs")),
    })
    return idea


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------

async def query_all_ideas() -> list[dict]:
    """Query Content Ideas DB, handling Notion pagination (100 per page).

    Returns list of idea dicts with list-level fields.
    """
    results = []
    has_more = True
    start_cursor = None

    async with httpx.AsyncClient() as client:
        while has_more:
            body: dict = {"page_size": 100}
            if start_cursor:
                body["start_cursor"] = start_cursor

            resp = await client.post(
                f"{NOTION_API_BASE}/databases/{NOTION_IDEAS_DB_ID}/query",
                headers=NOTION_HEADERS,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("results", []):
                results.append(_parse_idea_list(page))

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

    return results


async def get_idea_detail(page_id: str) -> dict:
    """Get a single idea page with ALL fields including hooks, captions, etc.

    Returns full idea dict with all list-level fields plus detail fields.
    Resolves Source Link relation to {name, url}.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{NOTION_API_BASE}/pages/{page_id}",
            headers=NOTION_HEADERS,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        page = resp.json()
        idea = _parse_idea_detail(page)

        # Resolve source_link relation
        source_link_ids = idea.pop("source_link_ids")
        idea["source_link"] = await _resolve_source_link(client, source_link_ids)

        return idea


async def get_ideas_stats() -> dict:
    """Return { total, by_status: {new: N, ...}, top_picks: N }."""
    ideas = await query_all_ideas()
    by_status: dict[str, int] = {}
    top_picks = 0

    for idea in ideas:
        status = idea["status"] or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        if idea["top_pick"]:
            top_picks += 1

    return {
        "total": len(ideas),
        "by_status": by_status,
        "top_picks": top_picks,
    }
