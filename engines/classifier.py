"""Classifier engine — core utilities for JSON parsing, transcript truncation,
and Obsidian knowledge-file writes, plus Notion integration and CLI.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import requests
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_LINKS_DB_ID = os.getenv("NOTION_LINKS_DB_ID")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
LOCAL_KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

MAX_RETRIES = 3
RETRY_BACKOFF = 2

PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / "prompts" / "classify_prompt.md"
CREATOR_CONTEXT_PATH = Path(__file__).parent.parent / "prompts" / "creator_context.md"

LOG_DIR = Path(__file__).parent.parent / "logs"


def _load_prompt_template() -> str:
    return PROMPT_TEMPLATE_PATH.read_text()


def _load_creator_context() -> str:
    return CREATOR_CONTEXT_PATH.read_text()


# ---------------------------------------------------------------------------
# Core utilities
# ---------------------------------------------------------------------------

def parse_classifier_output(raw_output: str) -> Optional[dict]:
    """Parse Claude's classification JSON output.

    Handles clean JSON, markdown fences, LLM preamble, trailing text,
    missing required fields, garbage, and empty input.
    """
    if not raw_output or not raw_output.strip():
        return None
    text = raw_output.strip()
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    if "tags" not in parsed or not isinstance(parsed["tags"], list):
        return None
    if "summary" not in parsed or not isinstance(parsed["summary"], str):
        return None
    return parsed


def truncate_transcript(text: str, max_words: int = 6000) -> str:
    """Truncate a long transcript to max_words and append a notice."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + f"\n\n[truncated — original was {len(words)} words]"


def _render_obsidian_tags(data) -> str:
    """Render obsidian_tags list as a Tags line. Returns empty string if no tags."""
    if isinstance(data, list):
        # hook_pattern passes a list of dicts — collect tags from all hooks
        all_tags = []
        for item in data:
            all_tags.extend(item.get("obsidian_tags", []))
        tags = list(dict.fromkeys(all_tags))  # dedupe preserving order
    else:
        tags = data.get("obsidian_tags", [])
    if not tags:
        return ""
    return "**Tags:** " + " ".join(f"#{t}" for t in tags)


def format_obsidian_entry(tag_type: str, data) -> str:
    """Format extracted data as markdown for an Obsidian knowledge file.

    Each tag_type produces a distinct markdown block. All blocks support
    an optional obsidian_tags array rendered as #tag format.
    """
    if tag_type == "content_lesson":
        tags_line = _render_obsidian_tags(data)
        parts = [
            f"## {data['title']}\n",
            f"{data['principle']}\n",
            f"**How to apply:** {data['how_to_apply']}\n",
        ]
        if tags_line:
            parts.append(f"{tags_line}\n")
        parts.append(f"**Source:** {data['source_author']}")
        parts.append(f"**Source URL:** {data['source_url']}")
        return "\n".join(parts)

    if tag_type == "hook_pattern":
        result_parts = []
        tags_line = _render_obsidian_tags(data)
        for hook in data:
            hook_parts = [
                f"### {hook['pattern'].title()}\n",
                f"> {hook['text']}\n",
            ]
            if tags_line:
                hook_parts.append(f"{tags_line}\n")
            hook_parts.append(f"**Source:** {hook['source_author']}")
            hook_parts.append(f"**Source URL:** {hook['source_url']}")
            result_parts.append("\n".join(hook_parts))
        return "\n\n".join(result_parts)

    if tag_type == "tool_discovery":
        tags_line = _render_obsidian_tags(data)
        parts = [
            f"## {data['name']}\n",
            f"{data['description']}\n",
            f"**Use case:** {data['use_case']}",
            f"**Link:** {data['link']}",
        ]
        if tags_line:
            parts.append(tags_line)
        parts.append(f"**Source:** {data['source_author']}")
        parts.append(f"**Source URL:** {data['source_url']}")
        return "\n".join(parts)

    if tag_type == "content_idea":
        tags_line = _render_obsidian_tags(data)
        parts = [
            f"## {data['title']}\n",
            f"**Angle:** {data['angle']}\n",
            f"{data['description']}\n",
        ]
        if tags_line:
            parts.append(f"{tags_line}\n")
        parts.append(f"**Source:** {data['source_author']}")
        parts.append(f"**Source URL:** {data['source_url']}")
        return "\n".join(parts)

    if tag_type == "workflow":
        tags_line = _render_obsidian_tags(data)
        parts = [
            f"## {data['title']}\n",
            f"**Steps:** {data['steps']}\n",
            f"**Why it works:** {data['why_it_works']}\n",
        ]
        if tags_line:
            parts.append(f"{tags_line}\n")
        parts.append(f"**Source:** {data['source_author']}")
        parts.append(f"**Source URL:** {data['source_url']}")
        return "\n".join(parts)

    raise ValueError(f"Unknown tag_type: {tag_type!r}")


def append_to_knowledge_file(file_path: Path, entry: str) -> bool:
    """Append entry to a knowledge file, deduplicating by Source URL.

    Returns False if the Source URL already exists in the file.
    Inserts a --- separator when the file does not already end with one.
    """
    url_match = re.search(r'\*\*Source URL:\*\*\s*(.+)', entry)
    if url_match and file_path.exists():
        source_url = url_match.group(1).strip()
        existing = file_path.read_text()
        if source_url in existing:
            return False
    existing = file_path.read_text() if file_path.exists() else ""
    if existing.rstrip().endswith("---"):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n{entry}\n")
    else:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n{entry}\n")
    return True


# ---------------------------------------------------------------------------
# Notion integration helpers
# ---------------------------------------------------------------------------

def notion_request(method, url, **kwargs):
    kwargs.setdefault("headers", NOTION_HEADERS)
    kwargs.setdefault("timeout", 15)
    resp = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = getattr(requests, method)(url, **kwargs)
            if resp.status_code < 500:
                return resp
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                print(f"    ⏳ Notion {resp.status_code}, retrying in {wait}s...")
                time.sleep(wait)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                print(f"    ⏳ {type(e).__name__}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
    return resp


def get_text_prop(props, key):
    prop = props.get(key, {})
    if prop.get("type") == "title":
        parts = prop.get("title", [])
    elif prop.get("type") == "rich_text":
        parts = prop.get("rich_text", [])
    else:
        return ""
    return parts[0]["plain_text"] if parts else ""


def get_select_prop(props, key):
    prop = props.get(key, {})
    sel = prop.get("select")
    return sel["name"] if sel else ""


def query_transcribed_links():
    """Query Notion for links with status=transcribed. Returns list of dicts."""
    results = []
    has_more = True
    start_cursor = None
    while has_more:
        body = {"filter": {"property": "Status", "select": {"equals": "transcribed"}}, "page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        resp = notion_request("post", f"https://api.notion.com/v1/databases/{NOTION_LINKS_DB_ID}/query", json=body)
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
                "transcript": get_text_prop(props, "Transcript"),
                "original_caption": get_text_prop(props, "Original Caption"),
                "author": get_text_prop(props, "Author"),
            })
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return results


def query_error_links():
    """Query Notion for links with status=classification_error. Returns list of dicts."""
    results = []
    has_more = True
    start_cursor = None
    while has_more:
        body = {"filter": {"property": "Status", "select": {"equals": "classification_error"}}, "page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        resp = notion_request("post", f"https://api.notion.com/v1/databases/{NOTION_LINKS_DB_ID}/query", json=body)
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
                "transcript": get_text_prop(props, "Transcript"),
                "original_caption": get_text_prop(props, "Original Caption"),
                "author": get_text_prop(props, "Author"),
            })
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return results


def log_classification_error(page_id, raw_output):
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"classify_error_{timestamp}_{page_id[:8]}.txt"
    log_file.write_text(f"Page ID: {page_id}\nTimestamp: {timestamp}\n\n{raw_output}")


def get_knowledge_dir():
    if OBSIDIAN_VAULT_PATH:
        vault_content = Path(OBSIDIAN_VAULT_PATH) / "content"
        if vault_content.exists():
            return vault_content
    LOCAL_KNOWLEDGE_DIR.mkdir(exist_ok=True)
    return LOCAL_KNOWLEDGE_DIR


def update_notion_classification(page_id, tags, summary):
    properties = {
        "Content Tags": {"multi_select": [{"name": t} for t in tags]},
        "AI Summary": {"rich_text": [{"text": {"content": summary[:2000]}}]},
        "Status": {"select": {"name": "classified"}},
    }
    resp = notion_request("patch", f"https://api.notion.com/v1/pages/{page_id}", json={"properties": properties})
    return resp.status_code == 200


def mark_classification_error(page_id):
    resp = notion_request("patch", f"https://api.notion.com/v1/pages/{page_id}", json={"properties": {"Status": {"select": {"name": "classification_error"}}}})
    return resp.status_code == 200


def classify_link(link, dry_run=False):
    """Classify a single link using Claude CLI and update Notion."""
    prompt = _load_prompt_template().replace("{creator_context}", _load_creator_context())
    prompt = prompt.replace("{transcript}", truncate_transcript(link["transcript"]))
    prompt = prompt.replace("{original_caption}", link.get("original_caption", "(none)"))
    prompt = prompt.replace("{source_url}", link.get("url", ""))
    prompt = prompt.replace("{author}", link.get("author", "unknown"))

    if dry_run:
        print(f"  Would classify: {link['name'][:60]}")
        return True

    print(f"  Classifying: {link['name'][:60]}")

    try:
        # Pipe prompt via stdin to avoid ARG_MAX
        result = subprocess.run(
            ["claude", "--model", "sonnet", "-p", "-"],
            input=prompt, capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        print(f"    ⏳ Timeout after 120s")
        log_classification_error(link["page_id"], "timeout")
        mark_classification_error(link["page_id"])
        return False

    if result.returncode != 0:
        print(f"    ❌ Claude CLI error: {result.stderr[:200]}")
        log_classification_error(link["page_id"], result.stderr)
        mark_classification_error(link["page_id"])
        return False

    parsed = parse_classifier_output(result.stdout)
    if parsed is None:
        # Retry once
        try:
            result = subprocess.run(
                ["claude", "--model", "sonnet", "-p", "-"],
                input=prompt, capture_output=True, text=True, timeout=120
            )
            parsed = parse_classifier_output(result.stdout)
        except subprocess.TimeoutExpired:
            pass

    if parsed is None:
        print(f"    ❌ Could not parse output")
        log_classification_error(link["page_id"], result.stdout if result else "no output")
        mark_classification_error(link["page_id"])
        return False

    tags = parsed["tags"]
    summary = parsed["summary"]
    if not update_notion_classification(link["page_id"], tags, summary):
        print(f"    ❌ Notion update failed")
        return False

    print(f"    ✅ Tags: {', '.join(tags)}")

    # Write insights to Obsidian knowledge files
    knowledge_dir = get_knowledge_dir()
    tag_to_file = {
        "content_lesson": "content-principles.md",
        "hook_pattern": "hook-bank.md",
        "tool_discovery": "tool-library.md",
        "content_idea": "idea-backlog.md",
        "workflow": "workflows.md",
    }
    # news is not persisted. inspiration takeaway is in AI Summary only.

    # Map tag names to JSON keys in Claude's output
    tag_to_json_key = {
        "content_lesson": "lesson",
        "hook_pattern": "hooks",
        "tool_discovery": "tool",
        "content_idea": "idea",
        "workflow": "workflow",
    }

    for tag in tags:
        json_key = tag_to_json_key.get(tag)
        if tag in tag_to_file and json_key and json_key in parsed:
            file_path = knowledge_dir / tag_to_file[tag]
            entry = format_obsidian_entry(tag, parsed[json_key])
            if entry:
                appended = append_to_knowledge_file(file_path, entry)
                if appended:
                    print(f"    📝 Added to {tag_to_file[tag]}")

    return True


# ---------------------------------------------------------------------------
# Batch runner and CLI
# ---------------------------------------------------------------------------

def classify_all_transcribed(dry_run=False, retry_errors=False):
    if retry_errors:
        links = query_error_links()
        print(f"Found {len(links)} links with classification_error")
    else:
        links = query_transcribed_links()
        print(f"Found {len(links)} transcribed links to classify")
    if not links:
        return 0
    classified = 0
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] {link['name'][:60]}")
        if classify_link(link, dry_run):
            classified += 1
    return classified


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    retry_errors = "--retry-errors" in args
    count = classify_all_transcribed(dry_run=dry_run, retry_errors=retry_errors)
    print(f"\n✅ Done: {count} classified")


if __name__ == "__main__":
    main()
