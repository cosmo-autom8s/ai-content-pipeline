"""Tests for engines/classifier.py — JSON parsing, truncation, and Obsidian writes."""

import pytest
from pathlib import Path
from engines.classifier import (
    parse_classifier_output,
    truncate_transcript,
    format_obsidian_entry,
    append_to_knowledge_file,
)


# ---------------------------------------------------------------------------
# parse_classifier_output
# ---------------------------------------------------------------------------

def test_parse_valid_json():
    raw = '{"tags": ["content_lesson"], "summary": "A valid summary."}'
    result = parse_classifier_output(raw)
    assert result is not None
    assert result["tags"] == ["content_lesson"]
    assert result["summary"] == "A valid summary."


def test_parse_json_in_markdown_fences():
    raw = '```json\n{"tags": ["hook_pattern"], "summary": "Summary in fences."}\n```'
    result = parse_classifier_output(raw)
    assert result is not None
    assert result["tags"] == ["hook_pattern"]
    assert result["summary"] == "Summary in fences."


def test_parse_json_with_preamble():
    raw = (
        "Sure! Here is the classification:\n\n"
        '{"tags": ["tool_discovery"], "summary": "Found a tool."}'
    )
    result = parse_classifier_output(raw)
    assert result is not None
    assert result["tags"] == ["tool_discovery"]
    assert result["summary"] == "Found a tool."


def test_parse_missing_tags_returns_none():
    raw = '{"summary": "No tags field here."}'
    result = parse_classifier_output(raw)
    assert result is None


def test_parse_garbage_returns_none():
    raw = "this is not json at all !!!"
    result = parse_classifier_output(raw)
    assert result is None


def test_parse_empty_returns_none():
    result = parse_classifier_output("")
    assert result is None


# ---------------------------------------------------------------------------
# truncate_transcript
# ---------------------------------------------------------------------------

def test_truncate_short_transcript():
    text = "word " * 100
    result = truncate_transcript(text.strip(), max_words=6000)
    assert result == text.strip()


def test_truncate_long_transcript():
    text = " ".join(["word"] * 10000)
    result = truncate_transcript(text, max_words=6000)
    word_count = len(result.split("[")[0].split())
    assert word_count == 6000


def test_truncate_adds_notice():
    text = " ".join(["word"] * 10000)
    result = truncate_transcript(text, max_words=6000)
    assert "[truncated — original was 10000 words]" in result


# ---------------------------------------------------------------------------
# format_obsidian_entry
# ---------------------------------------------------------------------------

def test_format_lesson_entry():
    data = {
        "title": "Hook-Payoff Gap",
        "principle": "The gap between hook and payoff drives engagement.",
        "how_to_apply": "Write the hook last, after the payoff is solid.",
        "source_author": "@creator",
        "source_url": "https://example.com/video",
    }
    result = format_obsidian_entry("content_lesson", data)
    assert "## Hook-Payoff Gap" in result
    assert "**How to apply:**" in result
    assert "**Source:** @creator" in result
    assert "**Source URL:**" in result


def test_format_hook_entry():
    data = [
        {
            "pattern": "contrarian",
            "text": "Stop posting every day.",
            "source_author": "@guru",
            "source_url": "https://example.com/hook",
        }
    ]
    result = format_obsidian_entry("hook_pattern", data)
    assert "Contrarian" in result or "contrarian" in result
    assert "Stop posting every day." in result


def test_format_tool_entry():
    data = {
        "name": "Descript",
        "description": "AI-powered video editor.",
        "use_case": "Remove filler words automatically.",
        "link": "https://descript.com",
        "source_author": "@editor",
        "source_url": "https://example.com/descript",
    }
    result = format_obsidian_entry("tool_discovery", data)
    assert "## Descript" in result
    assert "**Link:**" in result


def test_format_idea_entry():
    data = {
        "title": "AI tool teardown series",
        "angle": "Show the ugly before/after of using AI tools.",
        "description": "A weekly series dissecting AI tools for creators.",
        "source_author": "@ideas",
        "source_url": "https://example.com/idea",
    }
    result = format_obsidian_entry("content_idea", data)
    assert "## AI tool teardown series" in result
    assert "**Angle:**" in result
    assert "**Source URL:**" in result


def test_format_workflow_entry():
    data = {
        "title": "Batch-record-edit loop",
        "steps": "1. Record 3 videos. 2. Edit all at once. 3. Schedule.",
        "why_it_works": "Reduces context switching and increases output.",
        "source_author": "@workflow",
        "source_url": "https://example.com/workflow",
    }
    result = format_obsidian_entry("workflow", data)
    assert "## Batch-record-edit loop" in result
    assert "**Steps:**" in result or "steps" in result.lower()
    assert "**Source URL:**" in result


# ---------------------------------------------------------------------------
# append_to_knowledge_file
# ---------------------------------------------------------------------------

def test_append_creates_entry(tmp_path):
    knowledge_file = tmp_path / "lessons.md"
    entry = (
        "## Test Lesson\n\nSome principle.\n\n"
        "**Source:** @tester\n**Source URL:** https://example.com/test"
    )
    result = append_to_knowledge_file(knowledge_file, entry)
    assert result is True
    content = knowledge_file.read_text()
    assert "## Test Lesson" in content
    assert "**Source URL:** https://example.com/test" in content


def test_append_deduplicates_by_url(tmp_path):
    knowledge_file = tmp_path / "lessons.md"
    entry = (
        "## Duplicate Lesson\n\nSome principle.\n\n"
        "**Source:** @tester\n**Source URL:** https://example.com/duplicate"
    )
    # First write should succeed
    first = append_to_knowledge_file(knowledge_file, entry)
    assert first is True
    # Second write with the same URL should return False
    second = append_to_knowledge_file(knowledge_file, entry)
    assert second is False
