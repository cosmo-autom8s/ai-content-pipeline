"""Classifier engine — core utilities for JSON parsing, transcript truncation,
and Obsidian knowledge-file writes.
"""

import json
import re
from pathlib import Path
from typing import Optional, Union


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


def format_obsidian_entry(tag_type: str, data) -> str:
    """Format extracted data as markdown for an Obsidian knowledge file.

    Each tag_type produces a distinct markdown block:
      - content_lesson
      - hook_pattern  (data is a list of hook dicts)
      - tool_discovery
      - content_idea
      - workflow
    """
    if tag_type == "content_lesson":
        return (
            f"## {data['title']}\n\n"
            f"{data['principle']}\n\n"
            f"**How to apply:** {data['how_to_apply']}\n\n"
            f"**Source:** {data['source_author']}\n"
            f"**Source URL:** {data['source_url']}"
        )

    if tag_type == "hook_pattern":
        parts = []
        for hook in data:
            parts.append(
                f"### {hook['pattern'].title()}\n\n"
                f"> {hook['text']}\n\n"
                f"**Source:** {hook['source_author']}\n"
                f"**Source URL:** {hook['source_url']}"
            )
        return "\n\n".join(parts)

    if tag_type == "tool_discovery":
        return (
            f"## {data['name']}\n\n"
            f"{data['description']}\n\n"
            f"**Use case:** {data['use_case']}\n"
            f"**Link:** {data['link']}\n"
            f"**Source:** {data['source_author']}\n"
            f"**Source URL:** {data['source_url']}"
        )

    if tag_type == "content_idea":
        return (
            f"## {data['title']}\n\n"
            f"**Angle:** {data['angle']}\n\n"
            f"{data['description']}\n\n"
            f"**Source:** {data['source_author']}\n"
            f"**Source URL:** {data['source_url']}"
        )

    if tag_type == "workflow":
        return (
            f"## {data['title']}\n\n"
            f"**Steps:** {data['steps']}\n\n"
            f"**Why it works:** {data['why_it_works']}\n\n"
            f"**Source:** {data['source_author']}\n"
            f"**Source URL:** {data['source_url']}"
        )

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
