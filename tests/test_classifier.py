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


# ---------------------------------------------------------------------------
# Obsidian tag rendering
# ---------------------------------------------------------------------------

def test_format_lesson_with_obsidian_tags():
    data = {
        "title": "Hook-Payoff Gap",
        "principle": "The gap between hook and payoff drives engagement.",
        "how_to_apply": "Write the hook last.",
        "source_author": "@creator",
        "source_url": "https://example.com/video",
        "obsidian_tags": ["content-strategy", "hooks", "short-form"],
    }
    result = format_obsidian_entry("content_lesson", data)
    assert "**Tags:** #content-strategy #hooks #short-form" in result


def test_format_tool_with_obsidian_tags():
    data = {
        "name": "Descript",
        "description": "AI-powered video editor.",
        "use_case": "Remove filler words automatically.",
        "link": "https://descript.com",
        "source_author": "@editor",
        "source_url": "https://example.com/descript",
        "obsidian_tags": ["Descript", "video-editing", "AI-tools"],
    }
    result = format_obsidian_entry("tool_discovery", data)
    assert "**Tags:** #Descript #video-editing #AI-tools" in result


def test_format_hook_with_obsidian_tags():
    data = [
        {
            "pattern": "contrarian",
            "text": "Stop posting every day.",
            "source_author": "@guru",
            "source_url": "https://example.com/hook",
            "obsidian_tags": ["content-strategy", "posting-frequency"],
        }
    ]
    result = format_obsidian_entry("hook_pattern", data)
    assert "#content-strategy" in result
    assert "#posting-frequency" in result


def test_format_without_obsidian_tags_still_works():
    """Backward compat — no obsidian_tags key means no Tags line."""
    data = {
        "title": "Old Lesson",
        "principle": "Some principle.",
        "how_to_apply": "Apply it.",
        "source_author": "@old",
        "source_url": "https://example.com/old",
    }
    result = format_obsidian_entry("content_lesson", data)
    assert "**Tags:**" not in result
    assert "## Old Lesson" in result


# ---------------------------------------------------------------------------
# New knowledge tag types
# ---------------------------------------------------------------------------

def test_format_ai_knowledge_entry():
    data = {
        "title": "How Claude Skills Work",
        "knowledge": "Claude skills are markdown files with YAML frontmatter stored in ~/.claude/skills/.",
        "key_takeaways": ["Skills auto-load by context", "YAML frontmatter defines name and description"],
        "obsidian_tags": ["Claude", "Claude-Code", "skills"],
        "source_author": "rpn",
        "source_url": "https://example.com/skills",
    }
    result = format_obsidian_entry("ai_knowledge", data)
    assert "## How Claude Skills Work" in result
    assert "Claude skills are markdown files" in result
    assert "**Key takeaways:**" in result
    assert "Skills auto-load by context" in result
    assert "**Tags:** #Claude #Claude-Code #skills" in result
    assert "**Source:** rpn" in result
    assert "**Source URL:**" in result


def test_format_business_knowledge_entry():
    data = {
        "title": "The Sales Funnel as a Trust Gradient",
        "insight": "Each stage of the funnel earns a higher level of trust.",
        "how_to_apply": "Start with a low-friction first sale, then expand.",
        "obsidian_tags": ["sales", "funnels", "customer-journey"],
        "source_author": "gs2ai",
        "source_url": "https://example.com/funnels",
    }
    result = format_obsidian_entry("business_knowledge", data)
    assert "## The Sales Funnel as a Trust Gradient" in result
    assert "Each stage of the funnel" in result
    assert "**How to apply:**" in result
    assert "**Tags:** #sales #funnels #customer-journey" in result
    assert "**Source:** gs2ai" in result


def test_format_knowledge_nugget_entry():
    data = {
        "title": "Loss Aversion in Decision-Making",
        "knowledge": "People feel losses roughly twice as strongly as equivalent gains.",
        "why_it_matters": "Explains why businesses resist change even when the upside is clear.",
        "obsidian_tags": ["psychology", "decision-making", "behavioral-economics"],
        "source_author": "frankniu",
        "source_url": "https://example.com/loss-aversion",
    }
    result = format_obsidian_entry("knowledge_nugget", data)
    assert "## Loss Aversion in Decision-Making" in result
    assert "People feel losses roughly" in result
    assert "**Why it matters:**" in result
    assert "**Tags:** #psychology #decision-making #behavioral-economics" in result
    assert "**Source:** frankniu" in result


def test_format_news_entry():
    data = {
        "headline": "Anthropic releases Claude 4.5 with native tool use",
        "summary": "New Claude model supports direct tool execution without wrapper frameworks.",
        "why_it_matters": "Simplifies agent architectures for SMB automation use cases.",
        "obsidian_tags": ["Anthropic", "Claude", "agents"],
        "source_author": "ava.on.ai",
        "source_url": "https://example.com/news",
    }
    result = format_obsidian_entry("news", data)
    assert "## Anthropic releases Claude 4.5" in result
    assert "**Why it matters:**" in result
    assert "**Tags:** #Anthropic #Claude #agents" in result
    assert "**Source:** ava.on.ai" in result


# ---------------------------------------------------------------------------
# Heading-based deduplication
# ---------------------------------------------------------------------------

def test_append_deduplicates_tool_by_name(tmp_path):
    """When a tool entry with the same ## heading exists, skip it."""
    knowledge_file = tmp_path / "tool-library.md"
    entry1 = (
        "## Claude Code\n\nFirst description.\n\n"
        "**Source:** @first\n**Source URL:** https://example.com/first"
    )
    entry2 = (
        "## Claude Code\n\nSecond description from different source.\n\n"
        "**Source:** @second\n**Source URL:** https://example.com/second"
    )
    first = append_to_knowledge_file(knowledge_file, entry1)
    assert first is True
    second = append_to_knowledge_file(knowledge_file, entry2)
    assert second is False
    content = knowledge_file.read_text()
    assert content.count("## Claude Code") == 1


def test_append_allows_different_tool_names(tmp_path):
    """Different tool names should both be appended."""
    knowledge_file = tmp_path / "tool-library.md"
    entry1 = (
        "## Claude Code\n\nFirst tool.\n\n"
        "**Source:** @a\n**Source URL:** https://example.com/a"
    )
    entry2 = (
        "## Descript\n\nSecond tool.\n\n"
        "**Source:** @b\n**Source URL:** https://example.com/b"
    )
    append_to_knowledge_file(knowledge_file, entry1)
    result = append_to_knowledge_file(knowledge_file, entry2)
    assert result is True
    content = knowledge_file.read_text()
    assert "## Claude Code" in content
    assert "## Descript" in content


# ---------------------------------------------------------------------------
# Integration: parse + new tag types
# ---------------------------------------------------------------------------

def test_parse_output_with_new_knowledge_tags():
    """Full classifier output with new tag types parses correctly."""
    import json
    raw = json.dumps({
        "tags": ["ai_knowledge", "business_knowledge", "content_lesson"],
        "summary": "A video about AI funnels with both technical and business insights.",
        "ai_knowledge": {
            "title": "How to Build an AI Sales Funnel",
            "knowledge": "Chain Claude calls to qualify leads automatically.",
            "key_takeaways": ["Use structured output for lead scoring"],
            "obsidian_tags": ["Claude", "lead-gen", "funnels"],
            "source_author": "testauthor",
            "source_url": "https://example.com/test"
        },
        "business_knowledge": {
            "title": "The AI Sales Funnel as Revenue Engine",
            "insight": "AI funnels reduce cost-per-lead by automating qualification.",
            "how_to_apply": "Start with the highest-volume intake channel.",
            "obsidian_tags": ["sales", "funnels", "revenue"],
            "source_author": "testauthor",
            "source_url": "https://example.com/test"
        },
        "lesson": {
            "title": "Funnel Stages Map to Content Types",
            "principle": "Each funnel stage has a content type that moves people through it.",
            "how_to_apply": "Match your content to where your audience is in the journey.",
            "obsidian_tags": ["content-strategy", "funnels"],
            "source_author": "testauthor",
            "source_url": "https://example.com/test"
        }
    })
    result = parse_classifier_output(raw)
    assert result is not None
    assert "ai_knowledge" in result["tags"]
    assert "business_knowledge" in result["tags"]
    assert result["ai_knowledge"]["title"] == "How to Build an AI Sales Funnel"
    assert result["business_knowledge"]["insight"].startswith("AI funnels")
    assert result["lesson"]["obsidian_tags"] == ["content-strategy", "funnels"]
