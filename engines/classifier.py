"""Classifier engine — core utilities for JSON parsing, transcript truncation,
and Obsidian knowledge-file writes, plus Notion integration and CLI.
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_LINKS_DB_ID = os.getenv("NOTION_LINKS_DB_ID")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
LOCAL_KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "qwen/qwen3.6-plus:free")
CLASSIFIER_FALLBACK_MODEL = os.getenv("CLASSIFIER_FALLBACK_MODEL", "").strip()

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

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def validate_classifier_config() -> None:
    """Validate runtime configuration before making network calls."""
    missing = []
    if not NOTION_API_KEY:
        missing.append("NOTION_API_KEY")
    if not NOTION_LINKS_DB_ID:
        missing.append("NOTION_LINKS_DB_ID")
    if not OPENROUTER_API_KEY:
        missing.append("OPENROUTER_API_KEY")
    if missing:
        raise RuntimeError(f"Missing required classifier config: {', '.join(missing)}")
    if not PROMPT_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Classifier prompt template missing: {PROMPT_TEMPLATE_PATH}")
    if not CREATOR_CONTEXT_PATH.exists():
        raise RuntimeError(f"Creator context missing: {CREATOR_CONTEXT_PATH}")


def _openrouter_request(prompt: str, model: str) -> tuple[Optional[str], Optional[str]]:
    """Call OpenRouter for a single model attempt.

    Returns `(content, error_detail)`.
    """
    for attempt in range(3):
        resp = requests.post(
            url=OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }),
            timeout=120,
        )
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return None, f"{model}: empty choices in response"
            return choices[0].get("message", {}).get("content"), None
        if resp.status_code == 429 and attempt < 2:
            print(f"    ⏳ {model} rate limited, retrying in 30s (attempt {attempt + 1}/3)...")
            time.sleep(30)
            continue
        body_preview = resp.text[:400]
        return None, f"{model}: HTTP {resp.status_code} — {body_preview}"
    return None, f"{model}: exhausted retries after repeated rate limiting"


def _call_llm(prompt: str) -> tuple[Optional[str], Optional[str], str]:
    """Call OpenRouter with primary model and optional fallback model.

    Returns `(content, error_detail, model_used)`.
    """
    models = [CLASSIFIER_MODEL]
    if CLASSIFIER_FALLBACK_MODEL and CLASSIFIER_FALLBACK_MODEL != CLASSIFIER_MODEL:
        models.append(CLASSIFIER_FALLBACK_MODEL)

    error_messages = []
    for idx, model in enumerate(models):
        content, error_detail = _openrouter_request(prompt, model)
        if content is not None:
            return content, None, model
        if error_detail:
            error_messages.append(error_detail)
        if idx < len(models) - 1:
            print(f"    ⏳ Primary model unavailable, retrying with fallback: {models[idx + 1]}")

    return None, " | ".join(error_messages), models[0]


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

    if tag_type == "ai_knowledge":
        tags_line = _render_obsidian_tags(data)
        takeaways = data.get("key_takeaways", [])
        parts = [
            f"## {data['title']}\n",
            f"{data['knowledge']}\n",
        ]
        if takeaways:
            parts.append("**Key takeaways:**")
            for t in takeaways:
                parts.append(f"- {t}")
            parts.append("")
        if tags_line:
            parts.append(f"{tags_line}\n")
        parts.append(f"**Source:** {data['source_author']}")
        parts.append(f"**Source URL:** {data['source_url']}")
        return "\n".join(parts)

    if tag_type == "business_knowledge":
        tags_line = _render_obsidian_tags(data)
        parts = [
            f"## {data['title']}\n",
            f"{data['insight']}\n",
            f"**How to apply:** {data['how_to_apply']}\n",
        ]
        if tags_line:
            parts.append(f"{tags_line}\n")
        parts.append(f"**Source:** {data['source_author']}")
        parts.append(f"**Source URL:** {data['source_url']}")
        return "\n".join(parts)

    if tag_type == "knowledge_nugget":
        tags_line = _render_obsidian_tags(data)
        parts = [
            f"## {data['title']}\n",
            f"{data['knowledge']}\n",
            f"**Why it matters:** {data['why_it_matters']}\n",
        ]
        if tags_line:
            parts.append(f"{tags_line}\n")
        parts.append(f"**Source:** {data['source_author']}")
        parts.append(f"**Source URL:** {data['source_url']}")
        return "\n".join(parts)

    if tag_type == "news":
        tags_line = _render_obsidian_tags(data)
        date_str = datetime.now().strftime("%Y-%m-%d")
        parts = [
            f"## {data['headline']}\n",
            f"*{date_str}*\n",
            f"{data['summary']}\n",
            f"**Why it matters:** {data['why_it_matters']}\n",
        ]
        if tags_line:
            parts.append(f"{tags_line}\n")
        parts.append(f"**Source:** {data['source_author']}")
        parts.append(f"**Source URL:** {data['source_url']}")
        return "\n".join(parts)

    raise ValueError(f"Unknown tag_type: {tag_type!r}")


def append_to_knowledge_file(file_path: Path, entry: str) -> bool:
    """Append entry to a knowledge file, deduplicating by Source URL and heading.

    Returns False if:
    - The Source URL already exists in the file, OR
    - A markdown heading (## Title) from the entry already exists in the file.
    Inserts a --- separator when the file does not already end with one.
    """
    existing = file_path.read_text() if file_path.exists() else ""

    # Deduplicate by Source URL
    url_match = re.search(r'\*\*Source URL:\*\*\s*(.+)', entry)
    if url_match and existing:
        source_url = url_match.group(1).strip()
        if source_url in existing:
            return False

    # Deduplicate by heading (## Title or ### Title)
    heading_match = re.match(r'^(#{2,3})\s+(.+)', entry)
    if heading_match and existing:
        heading_level = heading_match.group(1)
        heading_text = heading_match.group(2).strip()
        if re.search(rf'^{re.escape(heading_level)}\s+{re.escape(heading_text)}\s*$', existing, re.MULTILINE):
            return False

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
        output, error_detail, model_used = _call_llm(prompt)
    except Exception as e:
        print(f"    ⏳ Error: {e}")
        log_classification_error(link["page_id"], str(e))
        mark_classification_error(link["page_id"])
        return False

    if output is None:
        print(f"    ❌ No usable response from OpenRouter")
        log_classification_error(link["page_id"], error_detail or "empty response")
        mark_classification_error(link["page_id"])
        return False

    parsed = parse_classifier_output(output)
    if parsed is None:
        # Retry once
        try:
            output, retry_error, retry_model = _call_llm(prompt)
            if output:
                parsed = parse_classifier_output(output)
                model_used = retry_model
            elif retry_error:
                error_detail = retry_error
        except Exception:
            pass

    if parsed is None:
        print(f"    ❌ Could not parse output")
        log_classification_error(link["page_id"], output or error_detail or "no output")
        mark_classification_error(link["page_id"])
        return False

    tags = parsed["tags"]
    summary = parsed["summary"]
    if not update_notion_classification(link["page_id"], tags, summary):
        print(f"    ❌ Notion update failed")
        return False

    print(f"    ✅ Tags: {', '.join(tags)}")
    print(f"    🧠 Model: {model_used}")

    # Write insights to Obsidian knowledge files
    knowledge_dir = get_knowledge_dir()
    tag_to_file = {
        "content_lesson": "content-principles.md",
        "hook_pattern": "hook-bank.md",
        "tool_discovery": "tool-library.md",
        "content_idea": "idea-backlog.md",
        "workflow": "workflows.md",
        "ai_knowledge": "ai-knowledge.md",
        "business_knowledge": "business-knowledge.md",
        "knowledge_nugget": "knowledge-nuggets.md",
        "news": "news.md",
    }

    # Map tag names to JSON keys in Claude's output
    tag_to_json_key = {
        "content_lesson": "lesson",
        "hook_pattern": "hooks",
        "tool_discovery": "tool",
        "content_idea": "idea",
        "workflow": "workflow",
        "ai_knowledge": "ai_knowledge",
        "business_knowledge": "business_knowledge",
        "knowledge_nugget": "knowledge_nugget",
        "news": "news_item",
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

def classify_all_transcribed(dry_run=False, retry_errors=False, limit=None):
    validate_classifier_config()
    if retry_errors:
        links = query_error_links()
        print(f"Found {len(links)} links with classification_error")
    else:
        links = query_transcribed_links()
        print(f"Found {len(links)} transcribed links to classify")
    if not links:
        return 0
    if limit:
        links = links[:limit]
        print(f"Limiting to first {limit} links")
    classified = 0
    api_delay = int(os.getenv("CLASSIFIER_DELAY", "5"))
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] {link['name'][:60]}")
        if classify_link(link, dry_run):
            classified += 1
        if not dry_run and i < len(links):
            time.sleep(api_delay)
    return classified


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    retry_errors = "--retry-errors" in args
    limit = None
    for arg in args:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
    count = classify_all_transcribed(dry_run=dry_run, retry_errors=retry_errors, limit=limit)
    print(f"\n✅ Done: {count} classified")


if __name__ == "__main__":
    main()
