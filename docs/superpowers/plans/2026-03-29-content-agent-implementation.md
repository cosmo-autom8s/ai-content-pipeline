# Content Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade content-pipeline-bot into a Content Agent with auto-classification, Obsidian knowledge files, and interactive `/ca-*` skills.

**Architecture:** Python classifier engine calls `claude -m sonnet` locally to tag transcripts and extract insights to Obsidian. Markdown skills guide Claude for interactive commands. CLAUDE.md makes the project conversational.

**Tech Stack:** Python 3.9+, Claude CLI (Sonnet), Notion API, Obsidian (direct filesystem writes), Claude Code skills (markdown)

**Spec:** `docs/superpowers/specs/2026-03-28-content-agent-design.md`

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `CLAUDE.md` | Project brain — tells Claude who it is, what context to read, how to behave |
| `engines/classifier.py` | Classification engine — queries Notion for transcribed links, calls Claude CLI, writes tags + knowledge |
| `prompts/classify_prompt.md` | Fabric-style extraction prompt consumed by classifier.py |
| `skills/ca-help.md` | Informational skill — lists all /ca-* commands with usage |
| `skills/ca-brief.md` | Morning brief skill — surfaces what's actionable |
| `skills/ca-classify.md` | Interactive classify skill — runs classifier, lets user adjust |
| `skills/ca-ideate.md` | Ideation skill — injects knowledge context into 4-skill pipeline |
| `skills/ca-research.md` | Research skill — web/GitHub search, save findings |
| `skills/ca-captions.md` | Captions skill — brand-aware caption generation |
| `skills/ca-sparring.md` | Sparring skill — creative discussion with knowledge context |
| `tests/test_classifier.py` | Tests for classifier JSON parsing, transcript truncation, Obsidian writes |

### Modified Files

| File | What Changes |
|------|-------------|
| `orchestrator.py` | Add classifier step after YouTube extraction (~5 lines) |
| `prompts/captions.txt` | Rewrite with full brand context (~80 lines replacing 17) |
| `.env` | Add `OBSIDIAN_VAULT_PATH` variable |

### Notion Changes (via MCP)

| Change | Details |
|--------|---------|
| New field: `Content Tags` | Multi-select on Links Queue |
| New field: `AI Summary` | Rich text on Links Queue |
| New status value: `classified` | Added to Status select |
| New status value: `classification_error` | Added to Status select |
| New view: `Classified` | Filtered by status=classified, grouped by Content Tags |

---

## Task 1: Notion Database Updates

Add new fields and status values to the Links Queue database via Notion MCP.

**Files:**
- Modify: Notion Links Queue database (via MCP, no file changes)
- Modify: `.env` (add OBSIDIAN_VAULT_PATH)

- [ ] **Step 1: Add `Content Tags` multi-select field to Links Queue**

Use Notion MCP to add the field. The database ID is in `.env` as `NOTION_LINKS_DB_ID` (value: `325a44c6f32f8086a1e4e1b10d6e6de9`).

Multi-select options to create: `content_idea`, `content_lesson`, `hook_pattern`, `tool_discovery`, `workflow`, `news`, `inspiration`

- [ ] **Step 2: Add `AI Summary` rich text field to Links Queue**

Use Notion MCP to add a rich text field called `AI Summary`.

- [ ] **Step 3: Add `classified` and `classification_error` to Status select options**

Use Notion MCP to update the Status select field. Add `classified` (between `transcribed` and `generate_ideas`) and `classification_error`.

- [ ] **Step 4: Create `Classified` view on Links Queue**

Use Notion MCP to create a new view filtered by `Status = classified`, grouped by `Content Tags`.

- [ ] **Step 5: Add OBSIDIAN_VAULT_PATH to .env**

```bash
echo '' >> .env
echo '# Obsidian vault path for knowledge files' >> .env
echo 'OBSIDIAN_VAULT_PATH=/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault' >> .env
```

- [ ] **Step 6: Verify all changes**

Query the Links Queue database via Notion MCP and confirm: `Content Tags` field exists, `AI Summary` field exists, `classified` status is available, `Classified` view is visible.

- [ ] **Step 7: Commit**

```bash
git add .env
git commit -m "chore: add OBSIDIAN_VAULT_PATH to env, Notion fields added via MCP"
```

---

## Task 2: Classification Prompt

Write the Fabric-style extraction prompt that the classifier engine will use.

**Files:**
- Create: `prompts/classify_prompt.md`

- [ ] **Step 1: Read existing prompts for style reference**

Read `prompts/creator_context.md` and `prompts/ideation_pipeline.md` to match the existing prompt style and ensure the classifier prompt references the right brand context.

- [ ] **Step 2: Write the classification prompt**

Create `prompts/classify_prompt.md` with the full Fabric-style structure. The prompt must include:

1. `# IDENTITY AND PURPOSE` section — content classification engine for Cosmo
2. `# CREATOR CONTEXT` section — placeholder `{creator_context}` that classifier.py injects
3. `# INPUT` section — placeholders `{transcript}`, `{original_caption}`, `{source_url}`, `{author}`
4. `# STEPS` section — classification logic (read transcript, identify tags, extract per tag type)
5. `# OUTPUT FORMAT` section — exact JSON schema with all tag-specific extraction structures:
   - `tags`: array of tag strings
   - `summary`: one-sentence summary
   - `lesson`: `{title, principle, how_to_apply, source_author, source_url}`
   - `hooks`: array of `{text, pattern, source_author, source_url}`
   - `tool`: `{name, description, use_case, link, source_author, source_url}`
   - `idea`: `{title, angle, description, filming_setup, source_author, source_url}`
   - `workflow`: `{title, steps, why_it_works, source_author, source_url}`
6. `# OUTPUT INSTRUCTIONS` section — rules for specificity, only include keys for applicable tags, extract actual insights not summaries

Reference the spec Section 3 "Extraction Prompt Structure" for the exact format.

- [ ] **Step 3: Commit**

```bash
git add prompts/classify_prompt.md
git commit -m "feat: add Fabric-style classification prompt"
```

---

## Task 3: Classifier Engine — Core Parsing & Obsidian Writes

Build the utility functions first: JSON parsing, transcript truncation, Obsidian file appending. Test them before building the main engine.

**Files:**
- Create: `engines/classifier.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: Write test for `parse_classifier_output`**

```python
# tests/test_classifier.py
import json
import pytest

def test_parse_valid_json():
    """Raw JSON string parses correctly."""
    from engines.classifier import parse_classifier_output
    raw = json.dumps({"tags": ["content_lesson"], "summary": "A lesson about hooks"})
    result = parse_classifier_output(raw)
    assert result["tags"] == ["content_lesson"]
    assert result["summary"] == "A lesson about hooks"

def test_parse_json_in_markdown_fences():
    """JSON wrapped in ```json ... ``` fences parses correctly."""
    from engines.classifier import parse_classifier_output
    raw = '```json\n{"tags": ["hook_pattern"], "summary": "Hook tips"}\n```'
    result = parse_classifier_output(raw)
    assert result["tags"] == ["hook_pattern"]

def test_parse_json_with_preamble():
    """JSON with LLM preamble text before it parses correctly."""
    from engines.classifier import parse_classifier_output
    raw = 'Here is the classification:\n\n{"tags": ["tool_discovery"], "summary": "A tool"}'
    result = parse_classifier_output(raw)
    assert result["tags"] == ["tool_discovery"]

def test_parse_missing_tags_returns_none():
    """JSON without required 'tags' field returns None."""
    from engines.classifier import parse_classifier_output
    raw = json.dumps({"summary": "No tags here"})
    result = parse_classifier_output(raw)
    assert result is None

def test_parse_garbage_returns_none():
    """Non-JSON garbage returns None."""
    from engines.classifier import parse_classifier_output
    result = parse_classifier_output("This is not JSON at all")
    assert result is None

def test_parse_empty_returns_none():
    """Empty string returns None."""
    from engines.classifier import parse_classifier_output
    result = parse_classifier_output("")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot
source venv/bin/activate
python -m pytest tests/test_classifier.py -v
```

Expected: FAIL — `engines/classifier` module not found.

- [ ] **Step 3: Implement `parse_classifier_output`**

Create `engines/classifier.py` with just the parsing function:

```python
#!/usr/bin/env python3
"""
Content Classifier Engine

Classifies transcribed links by calling Claude CLI (Sonnet) with a
Fabric-style extraction prompt. Writes tags to Notion and insights
to Obsidian knowledge files.

Usage:
    python engines/classifier.py              # Classify all transcribed links
    python engines/classifier.py --dry-run    # Preview what would be classified
    python engines/classifier.py --retry-errors  # Retry classification_error links
"""

from __future__ import annotations

import json
import re


def parse_classifier_output(raw_output: str) -> dict | None:
    """Parse Claude's classification output. Handles markdown fences and preamble."""
    if not raw_output or not raw_output.strip():
        return None

    text = raw_output.strip()

    # Strip markdown code fences if present
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        # Try to find JSON object in the text (skip preamble and trailing text)
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    # Validate required fields
    if not isinstance(parsed, dict):
        return None
    if "tags" not in parsed or not isinstance(parsed["tags"], list):
        return None
    if "summary" not in parsed or not isinstance(parsed["summary"], str):
        return None

    return parsed
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_classifier.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Write test for `truncate_transcript`**

Add to `tests/test_classifier.py`:

```python
def test_truncate_short_transcript():
    """Short transcripts are not truncated."""
    from engines.classifier import truncate_transcript
    text = "This is a short transcript."
    result = truncate_transcript(text, max_words=100)
    assert result == text

def test_truncate_long_transcript():
    """Long transcripts are cut to max_words."""
    from engines.classifier import truncate_transcript
    text = " ".join(["word"] * 10000)
    result = truncate_transcript(text, max_words=6000)
    word_count = len(result.split())
    assert word_count == 6000

def test_truncate_adds_notice():
    """Truncated transcripts end with a truncation notice."""
    from engines.classifier import truncate_transcript
    text = " ".join(["word"] * 10000)
    result = truncate_transcript(text, max_words=100)
    assert "[truncated — original was 10000 words]" in result
```

- [ ] **Step 6: Run test to verify it fails**

```bash
python -m pytest tests/test_classifier.py::test_truncate_short_transcript -v
```

Expected: FAIL — `truncate_transcript` not found.

- [ ] **Step 7: Implement `truncate_transcript`**

Add to `engines/classifier.py`:

```python
def truncate_transcript(text: str, max_words: int = 6000) -> str:
    """Truncate transcript to max_words. Adds [truncated] notice if cut."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + f"\n\n[truncated — original was {len(words)} words]"
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
python -m pytest tests/test_classifier.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 9: Write test for `format_obsidian_entry`**

Add to `tests/test_classifier.py`:

```python
def test_format_lesson_entry():
    """Lesson entry is formatted correctly for content-principles.md."""
    from engines.classifier import format_obsidian_entry
    lesson = {
        "title": "Hook-Payoff Gap",
        "principle": "The best hooks open a question the viewer needs closed.",
        "how_to_apply": "Open with a surprising claim. Let the gap sit.",
        "source_author": "@creator",
        "source_url": "https://tiktok.com/123"
    }
    entry = format_obsidian_entry("content_lesson", lesson)
    assert "## Hook-Payoff Gap" in entry
    assert "**How to apply:**" in entry
    assert "**Source:** @creator" in entry
    assert "**Source URL:** https://tiktok.com/123" in entry

def test_format_hook_entry():
    """Hook entry is formatted correctly for hook-bank.md."""
    from engines.classifier import format_obsidian_entry
    hooks = [
        {"text": "Stop posting every day.", "pattern": "contrarian",
         "source_author": "@creator", "source_url": "https://tiktok.com/123"}
    ]
    entry = format_obsidian_entry("hook_pattern", hooks)
    assert "### Contrarian" in entry or "contrarian" in entry.lower()
    assert "Stop posting every day." in entry

def test_format_tool_entry():
    """Tool entry is formatted correctly for tool-library.md."""
    from engines.classifier import format_obsidian_entry
    tool = {
        "name": "Descript",
        "description": "Video editing via transcript editing.",
        "use_case": "Speed up short-form editing.",
        "link": "https://descript.com",
        "source_author": "@creator",
        "source_url": "https://tiktok.com/123"
    }
    entry = format_obsidian_entry("tool_discovery", tool)
    assert "## Descript" in entry
    assert "**Link:**" in entry

def test_format_idea_entry():
    """Idea entry is formatted correctly for idea-backlog.md."""
    from engines.classifier import format_obsidian_entry
    idea = {
        "title": "AI tool teardown series",
        "angle": "Show the 5-min setup nobody talks about.",
        "source_author": "@creator",
        "source_url": "https://tiktok.com/456"
    }
    entry = format_obsidian_entry("content_idea", idea)
    assert "## AI tool teardown series" in entry
    assert "**Angle:**" in entry
    assert "**Source URL:** https://tiktok.com/456" in entry

def test_format_workflow_entry():
    """Workflow entry is formatted correctly for workflows.md."""
    from engines.classifier import format_obsidian_entry
    workflow = {
        "title": "Batch-record-edit loop",
        "steps": "Record 5 videos → batch edit → schedule over 2 weeks.",
        "source_author": "@creator",
        "source_url": "https://tiktok.com/789"
    }
    entry = format_obsidian_entry("workflow", workflow)
    assert "## Batch-record-edit loop" in entry
    assert "**Steps:**" in entry or "steps" in entry.lower()
    assert "**Source URL:** https://tiktok.com/789" in entry
```

- [ ] **Step 10: Implement `format_obsidian_entry`**

Add to `engines/classifier.py`. This function takes a tag type and the extracted data, returns formatted markdown string matching the spec's entry formats (Section 4).

- [ ] **Step 11: Run all tests**

```bash
python -m pytest tests/test_classifier.py -v
```

Expected: All 14 tests PASS.

- [ ] **Step 12: Write test for `append_to_knowledge_file`**

Add to `tests/test_classifier.py`:

```python
import tempfile
from pathlib import Path

def test_append_creates_entry(tmp_path):
    """Appending to a knowledge file adds the entry."""
    from engines.classifier import append_to_knowledge_file
    test_file = tmp_path / "test-principles.md"
    test_file.write_text("# Content Principles\n\n---\n")

    entry = "## Test Principle\nThis is a test.\n\n**Source URL:** https://example.com\n"
    append_to_knowledge_file(test_file, entry)

    content = test_file.read_text()
    assert "## Test Principle" in content
    assert "This is a test." in content

def test_append_deduplicates_by_url(tmp_path):
    """Appending with a URL that already exists in the file is skipped."""
    from engines.classifier import append_to_knowledge_file
    test_file = tmp_path / "test-principles.md"
    test_file.write_text("# Principles\n\n**Source URL:** https://example.com/123\n")

    entry = "## Duplicate\nShould be skipped.\n\n**Source URL:** https://example.com/123\n"
    appended = append_to_knowledge_file(test_file, entry)

    assert appended is False
    assert "## Duplicate" not in test_file.read_text()
```

- [ ] **Step 13: Implement `append_to_knowledge_file`**

Add to `engines/classifier.py`:

```python
def append_to_knowledge_file(file_path: Path, entry: str) -> bool:
    """Append an entry to a knowledge file. Returns False if URL already exists (dedup)."""
    # Extract source URL from entry for dedup check
    url_match = re.search(r'\*\*Source URL:\*\*\s*(.+)', entry)
    if url_match and file_path.exists():
        source_url = url_match.group(1).strip()
        existing = file_path.read_text()
        if source_url in existing:
            return False

    # Check if file already ends with a separator to avoid double ---
    existing = file_path.read_text() if file_path.exists() else ""
    if existing.rstrip().endswith("---"):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n{entry}\n")
    else:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n{entry}\n")
    return True
```

- [ ] **Step 14: Run all tests**

```bash
python -m pytest tests/test_classifier.py -v
```

Expected: All 16 tests PASS.

- [ ] **Step 15: Commit**

```bash
git add engines/classifier.py tests/test_classifier.py
git commit -m "feat: add classifier core — JSON parsing, truncation, Obsidian writes"
```

---

## Task 4: Classifier Engine — Notion Integration & CLI

Wire up the classifier to query Notion, call Claude CLI, and write results back.

**Files:**
- Modify: `engines/classifier.py`

- [ ] **Step 1: Add Notion imports and config**

Add to the top of `engines/classifier.py` (after existing imports):

```python
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

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

# Reuse retry logic from tokscript_parser
MAX_RETRIES = 3
RETRY_BACKOFF = 2

PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / "prompts" / "classify_prompt.md"
CREATOR_CONTEXT_PATH = Path(__file__).parent.parent / "prompts" / "creator_context.md"

def _load_prompt_template() -> str:
    return PROMPT_TEMPLATE_PATH.read_text()

def _load_creator_context() -> str:
    return CREATOR_CONTEXT_PATH.read_text()
```

- [ ] **Step 2: Add `notion_request` helper**

Copy the `notion_request` function from `extractors/tokscript_parser.py` (lines 47-69) — it has retry logic for timeouts and 5xx errors. Same pattern, reuse it.

- [ ] **Step 3: Add `query_transcribed_links` function**

Query Notion for links with `status=transcribed`. Follow the same pagination pattern as `engines/ideation.py:query_generate_ideas_links()` (lines 67-112). Return list of dicts with: `page_id`, `name`, `url`, `transcript`, `original_caption`, `author`.

Also add `query_error_links()` that queries `status=classification_error` for the `--retry-errors` flag.

- [ ] **Step 4: Add `log_classification_error` and `get_knowledge_dir` functions**

```python
LOG_DIR = Path(__file__).parent.parent / "logs"

def log_classification_error(page_id: str, raw_output: str):
    """Log classification errors for debugging. Writes raw Claude output to logs/."""
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"classify_error_{timestamp}_{page_id[:8]}.txt"
    log_file.write_text(f"Page ID: {page_id}\nTimestamp: {timestamp}\n\n{raw_output}")
```

Add `get_knowledge_dir`:

```python
def get_knowledge_dir() -> Path:
    """Get the knowledge files directory. Uses Obsidian vault if available, else local fallback."""
    if OBSIDIAN_VAULT_PATH:
        vault_content = Path(OBSIDIAN_VAULT_PATH) / "content"
        if vault_content.exists():
            return vault_content
    # Fallback to local
    LOCAL_KNOWLEDGE_DIR.mkdir(exist_ok=True)
    return LOCAL_KNOWLEDGE_DIR
```

- [ ] **Step 5: Add `update_notion_tags` and `update_notion_summary` functions**

```python
def update_notion_classification(page_id: str, tags: list, summary: str) -> bool:
    """Update a link's Content Tags, AI Summary, and status to classified."""
    properties = {
        "Content Tags": {"multi_select": [{"name": t} for t in tags]},
        "AI Summary": {"rich_text": [{"text": {"content": summary[:2000]}}]},
        "Status": {"select": {"name": "classified"}},
    }
    resp = notion_request("patch",
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": properties},
    )
    return resp.status_code == 200

def mark_classification_error(page_id: str) -> bool:
    """Mark a link as classification_error."""
    resp = notion_request("patch",
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": {"Status": {"select": {"name": "classification_error"}}}},
    )
    return resp.status_code == 200
```

- [ ] **Step 6: Add `classify_link` main function**

```python
def classify_link(link: dict, dry_run: bool = False) -> bool:
    """Classify a single link. Returns True on success."""
    prompt = _load_prompt_template().replace("{creator_context}", _load_creator_context())
    prompt = prompt.replace("{transcript}", truncate_transcript(link["transcript"]))
    prompt = prompt.replace("{original_caption}", link.get("original_caption", "(none)"))
    prompt = prompt.replace("{source_url}", link.get("url", ""))
    prompt = prompt.replace("{author}", link.get("author", "unknown"))

    if dry_run:
        print(f"  Would classify: {link['name'][:60]}")
        return True

    print(f"  Classifying: {link['name'][:60]}")

    # Call Claude CLI locally (Sonnet)
    try:
        # Pipe prompt via stdin to avoid ARG_MAX shell limits
        result = subprocess.run(
            ["claude", "-m", "sonnet", "-p", "-"],
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

    # Parse output
    parsed = parse_classifier_output(result.stdout)
    if parsed is None:
        # Retry once
        try:
            result = subprocess.run(
                ["claude", "-m", "sonnet", "-p", "-"],
                input=prompt, capture_output=True, text=True, timeout=120
            )
            parsed = parse_classifier_output(result.stdout)
        except subprocess.TimeoutExpired:
            pass

    if parsed is None:
        print(f"    ❌ Could not parse output")
        mark_classification_error(link["page_id"])
        return False

    # Write to Notion
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
    # Note: `news` is not persisted. `inspiration` takeaway is captured in the AI Summary field only.

    for tag in tags:
        if tag in tag_to_file and tag in parsed:
            file_path = knowledge_dir / tag_to_file[tag]
            entry = format_obsidian_entry(tag, parsed[tag])
            if entry:
                appended = append_to_knowledge_file(file_path, entry)
                if appended:
                    print(f"    📝 Added to {tag_to_file[tag]}")

    return True
```

- [ ] **Step 7: Add `classify_all_transcribed` and `main` functions**

```python
def classify_all_transcribed(dry_run: bool = False, retry_errors: bool = False) -> int:
    """Classify all transcribed (or error) links. Returns count classified."""
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
```

- [ ] **Step 8: Manual test with dry run**

```bash
source venv/bin/activate
python engines/classifier.py --dry-run
```

Expected: Shows list of transcribed links that would be classified.

- [ ] **Step 9: Manual test with one real link**

Pick one transcribed link from the dry run output and test the full flow:

```bash
python engines/classifier.py
```

Verify: link status changes to `classified` in Notion, Content Tags populated, AI Summary written, knowledge file entry appended in Obsidian (or local fallback).

- [ ] **Step 10: Commit**

```bash
git add engines/classifier.py
git commit -m "feat: add classifier engine with Notion integration and Claude CLI"
```

---

## Task 5: Orchestrator Integration

Wire the classifier into the evening pipeline.

**Files:**
- Modify: `orchestrator.py` (add ~10 lines)

- [ ] **Step 1: Read the current orchestrator**

Read `orchestrator.py` to find the exact insertion point (after YouTube extraction, before the summary section).

- [ ] **Step 2: Add classifier import**

Add to the imports at top of `orchestrator.py` (around line 34, after other imports):

```python
from engines.classifier import classify_all_transcribed
```

- [ ] **Step 3: Add classifier step in `main()`**

Insert after the YouTube extraction block (around line 266, before "Step 5: Summary"), add:

```python
    # Step 4: Classify newly transcribed links
    print("Classifying transcribed links...")
    if not dry_run:
        classified_count = classify_all_transcribed()
        print(f"\nClassification: {classified_count} links classified")
    else:
        classified_count = classify_all_transcribed(dry_run=True)
        print(f"\nClassification: {classified_count} links would be classified")
    print()
```

- [ ] **Step 4: Update the summary "Next steps" section**

Update the summary at the end of `main()` to mention classification:

```python
    print("  1. Review classified links in Notion 'Classified' view")
    print("  2. Tag links for ideation: python engines/ideation.py --list")
    print("  3. Generate ideas: /ca-ideate")
    print("  4. Review Morning Menu in Notion")
```

- [ ] **Step 5: Test with dry run**

```bash
source venv/bin/activate
python orchestrator.py --dry-run
```

Expected: Shows existing pipeline steps + "Classification: X links would be classified"

- [ ] **Step 6: Commit**

```bash
git add orchestrator.py
git commit -m "feat: wire classifier into evening orchestrator pipeline"
```

---

## Task 6: Knowledge File Seeds

Create initial knowledge files with headers so the classifier has files to append to. Uses local fallback dir if Obsidian isn't set up yet.

**Files:**
- Create: Knowledge files (5 files in Obsidian vault or local `knowledge/` dir)

- [ ] **Step 1: Check if Obsidian vault path is accessible**

```bash
ls "/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault/content/" 2>/dev/null || echo "Need to create content/ dir"
```

- [ ] **Step 2: Create the knowledge files directory**

If Obsidian vault is accessible:
```bash
mkdir -p "/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault/content/"
```

If not, use local fallback:
```bash
mkdir -p knowledge/
```

- [ ] **Step 3: Seed `content-principles.md`**

```markdown
# Content Principles

Running playbook of content creation lessons extracted from saved videos. Each entry is a transferable principle with application notes.

---
```

- [ ] **Step 4: Seed `hook-bank.md`**

```markdown
# Hook Bank

Collected opening lines and patterns from saved videos, categorized by type.

### Authority

### Contrarian

### Data

### Story

### Cautionary

---
```

- [ ] **Step 5: Seed `tool-library.md`**

```markdown
# Tool Library

Tools discovered from saved videos. Each entry includes what it does and potential use case.

---
```

- [ ] **Step 6: Seed `idea-backlog.md`**

```markdown
# Idea Backlog

Content ideas extracted from saved videos. Each entry has an angle and filming setup.

---
```

- [ ] **Step 7: Seed `workflows.md`**

```markdown
# Workflows

Processes and workflows worth studying or copying, extracted from saved videos.

---
```

- [ ] **Step 8: Commit (if using local fallback)**

```bash
git add knowledge/
git commit -m "feat: seed knowledge files for classifier output"
```

Note: If files are in Obsidian vault, they're outside the git repo — no commit needed.

---

## Task 7: CLAUDE.md

Create the project brain that makes the project conversational.

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write CLAUDE.md**

Create `CLAUDE.md` at project root. Include:
1. Who the agent is (content sparring partner)
2. Context files to read (creator_context.md, all knowledge file paths with the vault path from .env)
3. All `/ca-*` slash commands with one-line descriptions
4. Behavior rules (lead with actionable, push back on weak ideas, output-biased, reference knowledge files)
5. Operating principles from Cosmo's vault (volume before optimization, challenge timelines, don't let him hide)
6. Notion database IDs for reference
7. Note about knowledge files location (Obsidian vault or local fallback)

Reference the spec Section 5 "CLAUDE.md" for the template.

- [ ] **Step 2: Verify by opening a new Claude Code session**

Open a new terminal, `cd` into the project, start `claude`. Verify it reads the CLAUDE.md. Ask it "what can you do?" and confirm it references the `/ca-*` commands.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "feat: add CLAUDE.md — project brain for Content Agent"
```

---

## Task 8: Skills — /ca-help and /ca-classify

Build the simplest skills first.

**Files:**
- Create: `skills/ca-help.md`
- Create: `skills/ca-classify.md`

- [ ] **Step 1: Create `skills/` directory**

```bash
mkdir -p skills/
```

- [ ] **Step 2: Write `skills/ca-help.md`**

Pure informational skill. Include:
- Skill frontmatter (`name`, `description`)
- One-line description of the Content Agent
- Table of all `/ca-*` commands: name, what it does, example usage
- Quick tips section ("Just talk to me for freeform sparring", "Run /ca-brief every morning")
- Knowledge files section — where they live, what each one contains

- [ ] **Step 3: Write `skills/ca-classify.md`**

Skill that instructs Claude to:
1. Run `python engines/classifier.py --dry-run` first to show what would be classified
2. Ask user to confirm or pick specific links
3. Run `python engines/classifier.py` to classify
4. Show results summary
5. Offer to adjust tags via Notion MCP if user disagrees with any classification
6. Support `--retry-errors` argument to re-attempt failed classifications

- [ ] **Step 4: Test both skills**

Start a Claude Code session in the project. Run `/ca-help` and `/ca-classify` to verify they load and work.

- [ ] **Step 5: Commit**

```bash
git add skills/ca-help.md skills/ca-classify.md
git commit -m "feat: add /ca-help and /ca-classify skills"
```

---

## Task 9: Skills — /ca-brief and /ca-sparring

**Files:**
- Create: `skills/ca-brief.md`
- Create: `skills/ca-sparring.md`

- [ ] **Step 1: Write `skills/ca-brief.md`**

Skill that instructs Claude to:
1. Query Notion via MCP: count links by status (transcribed, classified, generate_ideas) from the past 7 days
2. Query Notion via MCP: Content Ideas DB — count by status (new, queued, filming_today, filmed)
3. Read knowledge files: last 5 entries from each file (content-principles, hook-bank, tool-library, idea-backlog)
4. Synthesize into a brief with these sections:
   - Pipeline status ("X saved this week, Y classified, Z awaiting triage")
   - Top 3 actionable content ideas (from Content Ideas DB, sorted by score)
   - 1 principle from this week's knowledge files
   - 1 tool worth mentioning
   - Filming queue status
5. Include Notion database IDs in the skill so Claude knows which DBs to query

- [ ] **Step 2: Write `skills/ca-sparring.md`**

Pure conversational skill that instructs Claude to:
1. Read `prompts/creator_context.md` for brand voice and ICP
2. Read all knowledge files for accumulated context
3. Enter creative discussion mode with rules:
   - Push back on generic ideas — reference specific principles from knowledge files
   - Challenge weak angles — "Could any competitor say this?"
   - Suggest hooks from the hook bank
   - Stay practical — "Can you film this in 30 minutes?"
   - Bias toward output, not analysis
   - No auto-save — the user decides what to act on

- [ ] **Step 3: Test both skills**

Start a Claude Code session. Run `/ca-brief` (should query Notion and produce a brief). Run `/ca-sparring` and test with a content topic.

- [ ] **Step 4: Commit**

```bash
git add skills/ca-brief.md skills/ca-sparring.md
git commit -m "feat: add /ca-brief and /ca-sparring skills"
```

---

## Task 10: Skills — /ca-ideate and /ca-captions

**Files:**
- Create: `skills/ca-ideate.md`
- Create: `skills/ca-captions.md`
- Modify: `prompts/captions.txt`

- [ ] **Step 1: Write `skills/ca-ideate.md`**

Skill that instructs Claude to:
1. If user provides a topic: ideate freely on that topic
   If no topic: run `python engines/ideation.py --list` to get links tagged `generate_ideas`
2. Read knowledge files for context: `content-principles.md`, `hook-bank.md`, `idea-backlog.md`
3. Read `prompts/creator_context.md` for brand/voice/ICP
4. Read `prompts/ideation_pipeline.md` for the 4-skill pipeline instructions
5. Run the pipeline: idea-gen → hooks → creative-director → de-AI-ify
6. Present ideas for review
7. Save approved ideas via Notion MCP or `engines/ideation.py --save`
8. Note the key difference: knowledge files are context, so ideas reflect accumulated learning

- [ ] **Step 2: Rewrite `prompts/captions.txt` with full brand context**

Replace the existing 17-line prompt with a comprehensive caption prompt that includes:
- Brand voice reference (from `creator_context.md`)
- Platform-specific rules (TikTok, IG, YouTube, LinkedIn) — expanded from current
- Hook-first principle
- CTA patterns per platform
- Language rules (no vendor language, use their language)
- Words to avoid list
- Output format (same JSON structure as current)

- [ ] **Step 3: Write `skills/ca-captions.md`**

Skill that instructs Claude to:
1. Run `python engines/captions.py --list` to get filmed ideas
2. Read `prompts/creator_context.md` for brand voice
3. Read `prompts/captions.txt` for the updated caption prompt
4. Read `content-principles.md` and `hook-bank.md` for latest knowledge
5. Generate captions for each filmed idea
6. Present for review
7. Save via Notion MCP (update the idea page with platform captions)

- [ ] **Step 4: Test both skills**

Start a Claude Code session. Run `/ca-ideate` (should show queued links or ask for a topic). Run `/ca-captions` (should show filmed ideas or say none found).

- [ ] **Step 5: Commit**

```bash
git add skills/ca-ideate.md skills/ca-captions.md prompts/captions.txt
git commit -m "feat: add /ca-ideate and /ca-captions skills, rewrite captions prompt"
```

---

## Task 11: Skill — /ca-research

**Files:**
- Create: `skills/ca-research.md`

- [ ] **Step 1: Write `skills/ca-research.md`**

Conversational skill that instructs Claude to:
1. Take the user's topic as input
2. Use built-in web search to find: articles, blog posts, tools, repos, trending discussions
3. Organize findings into sections: Key Findings, Tools Discovered, Content Angles, Sources
4. Ask if user wants to save any findings to knowledge files:
   - Tools → append to `tool-library.md`
   - Lessons → append to `content-principles.md`
   - Ideas → append to `idea-backlog.md`
5. Keep output practical and action-oriented — what can you FILM from this research?

- [ ] **Step 2: Test the skill**

Start a Claude Code session. Run `/ca-research AI content agents` and verify it searches, organizes, and offers to save.

- [ ] **Step 3: Commit**

```bash
git add skills/ca-research.md
git commit -m "feat: add /ca-research skill"
```

---

## Task 12: Update README and Plan

Update project documentation to reflect the Content Agent upgrade.

**Files:**
- Modify: `README.md`
- Modify: `CONTENT_ENGINE_PLAN.md`

- [ ] **Step 1: Update README.md**

Add a "Content Agent" section that covers:
- What the Content Agent is (one paragraph)
- The `/ca-*` commands table
- Updated daily workflow (now includes classification step)
- Knowledge files description
- Updated file structure

Keep existing sections (Quick Start, Telegram Bot Commands, etc.) and update where needed.

- [ ] **Step 2: Update CONTENT_ENGINE_PLAN.md**

- Update "Current State" to reflect the Content Agent upgrade
- Move completed backlog items
- Add new backlog items for future work (scheduled classification, weekly digest, trend detection)
- Update version history

- [ ] **Step 3: Commit**

```bash
git add README.md CONTENT_ENGINE_PLAN.md
git commit -m "docs: update README and plan for Content Agent upgrade"
```

---

## Task 13: End-to-End Test

Run the full pipeline to verify everything works together.

- [ ] **Step 1: Run the orchestrator**

```bash
source venv/bin/activate
python orchestrator.py --dry-run
```

Verify: CSV inbox → YouTube extraction → Classification step all show correctly.

- [ ] **Step 2: Run the classifier on real data**

```bash
python engines/classifier.py
```

Verify in Notion: links have Content Tags, AI Summary, and status=classified.

- [ ] **Step 3: Check knowledge files**

Verify that Obsidian (or local) knowledge files have new entries from the classification.

- [ ] **Step 4: Test interactive skills**

In a new Claude Code session:
- `/ca-help` — shows all commands
- `/ca-brief` — produces a morning brief
- `/ca-classify` — shows classified links
- `/ca-sparring` — have a content conversation
- Ask a freeform question: "What hooks have I saved?" — should reference hook-bank.md

- [ ] **Step 5: Run the test suite**

```bash
python -m pytest tests/test_classifier.py -v
```

Expected: All tests pass.

- [ ] **Step 6: Final commit**

```bash
git add engines/ prompts/ tests/ knowledge/ .claude/ orchestrator.py README.md CLAUDE.md
git commit -m "feat: Content Agent v2.0 — classification, knowledge files, /ca-* skills"
```
