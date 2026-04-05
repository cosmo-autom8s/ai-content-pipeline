# Classifier V2: Knowledge Tags, Obsidian Tags, and Non-Exclusive Extraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the classifier to extract knowledge into dedicated files (`ai_knowledge`, `business_knowledge`, `knowledge_nugget`), add Obsidian-native `#tags` to every entry, support non-exclusive tagging (same content → multiple files with different framing), and improve deduplication.

**Architecture:** The classify prompt gets 3 new tag types with distinct JSON schemas, plus an `obsidian_tags` array on every extracted object. The classifier engine gets new mappings, format functions, and tag rendering. Knowledge files are non-exclusive — a video about AI funnels can produce entries in both `ai-knowledge.md` (technical framing) and `business-knowledge.md` (strategy framing) simultaneously.

**Tech Stack:** Python, pytest, Claude CLI (via subprocess), Notion API, Obsidian markdown files

---

## File Structure

| File | Role | Action |
|------|------|--------|
| `engines/classifier.py` | Classification engine — tag mappings, format functions, file writes | Modify |
| `tests/test_classifier.py` | Unit tests for classifier core functions | Modify |
| `prompts/classify_prompt.md` | Fabric-style prompt template for Claude | Modify |
| Obsidian: `content/ai-knowledge.md` | AI-specific knowledge (tools, techniques, architecture) | Create |
| Obsidian: `content/business-knowledge.md` | Business strategy, sales, operations knowledge | Create |
| Obsidian: `content/knowledge-nuggets.md` | General knowledge (psychology, economics, mental models) | Create |
| Obsidian: `content/news.md` | Timestamped industry news log | Create |
| `CLAUDE.md` | Project brain — knowledge file table | Modify |
| `skills/ca-help.md` | Help reference — knowledge file table | Modify |

**Obsidian vault path:** `/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault/content/`

**Key design decisions:**
- `obsidian_tags` is an array of strings output by Claude for every extracted object (e.g. `["Claude", "skills", "tutorial"]`). The format function prepends `#` and renders them as a `**Tags:** #Claude #skills #tutorial` line.
- Tags are NOT exclusive. The `tags` array in Claude's output can contain `["ai_knowledge", "business_knowledge", "content_lesson"]` simultaneously. Each produces a separate entry in its respective file, with framing appropriate to that file's purpose.
- Tool deduplication switches from URL-only to URL-or-name matching for `tool_discovery` entries.
- The `news` tag now persists to `news.md` with a date stamp.

---

### Task 1: Add Obsidian tag rendering to existing format functions

**Context:** Every `format_obsidian_entry` branch currently outputs markdown without Obsidian tags. We need to add a `**Tags:**` line to every entry type, reading from an `obsidian_tags` array in the data dict. This is backward-compatible — if `obsidian_tags` is missing, no Tags line is rendered.

**Files:**
- Modify: `engines/classifier.py:92-150` (format_obsidian_entry function)
- Modify: `tests/test_classifier.py`

- [ ] **Step 1: Write failing tests for Obsidian tag rendering**

Add these tests to `tests/test_classifier.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v -k "obsidian_tags or without_obsidian_tags"`

Expected: FAIL — `"**Tags:** #content-strategy #hooks #short-form"` not found in output.

- [ ] **Step 3: Implement tag rendering helper and update format_obsidian_entry**

In `engines/classifier.py`, add a helper function right before `format_obsidian_entry` (around line 91):

```python
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
```

Then update each branch in `format_obsidian_entry` to append the tags line. The pattern is the same for each — insert the tags line between the last content line and the Source lines. Example for `content_lesson`:

```python
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
```

Apply the same pattern to all 5 existing branches (`content_lesson`, `hook_pattern`, `tool_discovery`, `content_idea`, `workflow`). For `hook_pattern`, pass the list directly to `_render_obsidian_tags`. The tags line goes before the Source lines in each hook block.

Full replacement for `format_obsidian_entry`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v`

Expected: ALL tests pass (existing + new obsidian tag tests).

- [ ] **Step 5: Commit**

```bash
git add engines/classifier.py tests/test_classifier.py
git commit -m "feat: add Obsidian #tag rendering to all format_obsidian_entry types"
```

---

### Task 2: Add new knowledge tag types (ai_knowledge, business_knowledge, knowledge_nugget)

**Context:** Three new tag types need format functions, tag-to-file mappings, and tag-to-JSON-key mappings. Each produces differently framed entries:
- `ai_knowledge` → technical AI knowledge (how tools work, setup guides, architecture)
- `business_knowledge` → business strategy, sales, operations, market dynamics
- `knowledge_nugget` → general knowledge not AI or business specific (psychology, mental models, economics)

**Files:**
- Modify: `engines/classifier.py`
- Modify: `tests/test_classifier.py`

- [ ] **Step 1: Write failing tests for new format types**

Add to `tests/test_classifier.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v -k "ai_knowledge or business_knowledge or knowledge_nugget"`

Expected: FAIL — `ValueError: Unknown tag_type: 'ai_knowledge'`

- [ ] **Step 3: Add format branches for new tag types**

In `engines/classifier.py`, add three new branches to `format_obsidian_entry` before the `raise ValueError` line:

```python
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
```

- [ ] **Step 4: Add tag-to-file and tag-to-JSON-key mappings**

In `engines/classifier.py`, in the `classify_link` function, update both dicts:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v`

Expected: ALL tests pass.

- [ ] **Step 6: Commit**

```bash
git add engines/classifier.py tests/test_classifier.py
git commit -m "feat: add ai_knowledge, business_knowledge, knowledge_nugget tag types"
```

---

### Task 3: Add news persistence with date stamps

**Context:** The `news` tag currently doesn't persist anywhere — it's tag-only. We'll add a format function that produces a dated entry for `news.md`.

**Files:**
- Modify: `engines/classifier.py`
- Modify: `tests/test_classifier.py`

- [ ] **Step 1: Write failing test for news format**

Add to `tests/test_classifier.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v -k "test_format_news"`

Expected: FAIL — `ValueError: Unknown tag_type: 'news'`

- [ ] **Step 3: Add news format branch**

In `engines/classifier.py`, add before the `raise ValueError` line:

```python
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
```

Note: `datetime` is already imported at the top of `classifier.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v`

Expected: ALL tests pass.

- [ ] **Step 5: Commit**

```bash
git add engines/classifier.py tests/test_classifier.py
git commit -m "feat: add news persistence with date stamps"
```

---

### Task 4: Tool name-based deduplication

**Context:** `append_to_knowledge_file` currently deduplicates by Source URL only. Tool entries like "Claude Code" appear 3 times from 3 different source videos. We need name-based dedup for `tool_discovery` entries: if `## Tool Name` already exists, append the new source as a reference instead of creating a duplicate.

**Files:**
- Modify: `engines/classifier.py:153-172` (append_to_knowledge_file)
- Modify: `tests/test_classifier.py`

- [ ] **Step 1: Write failing tests for name-based dedup**

Add to `tests/test_classifier.py`:

```python
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
    # File should only contain the first entry
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v -k "deduplicates_tool"`

Expected: FAIL — `test_append_deduplicates_tool_by_name` fails because the second entry has a different URL so it gets appended.

- [ ] **Step 3: Add heading-based dedup to append_to_knowledge_file**

Replace the `append_to_knowledge_file` function in `engines/classifier.py`:

```python
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
        # Check if the same heading already exists
        if re.search(rf'^{re.escape(heading_level)}\s+{re.escape(heading_text)}\s*$', existing, re.MULTILINE):
            return False

    if existing.rstrip().endswith("---"):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n{entry}\n")
    else:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n{entry}\n")
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v`

Expected: ALL tests pass (including existing dedup-by-URL test).

- [ ] **Step 5: Commit**

```bash
git add engines/classifier.py tests/test_classifier.py
git commit -m "feat: add heading-based deduplication for tool entries"
```

---

### Task 5: Update classify prompt with new tags, non-exclusive framing, and Obsidian tags

**Context:** The prompt at `prompts/classify_prompt.md` needs to:
1. Add 3 new tag types (`ai_knowledge`, `business_knowledge`, `knowledge_nugget`) with JSON schemas
2. Update `news` to include a JSON extraction object (no longer tag-only)
3. Add `obsidian_tags` to every extracted object
4. Explain non-exclusive tagging: same content can appear under multiple knowledge tags with different framing
5. Explain what Obsidian tags should contain (tool names, topic keywords, source type)

**Files:**
- Modify: `prompts/classify_prompt.md`

- [ ] **Step 1: Update the tag list in STEPS section**

Replace the tag list (lines 39-47) with:

```markdown
2. Identify which tags apply from this list:
   - `content_idea` — the content itself (or a variation of it) could be filmed by Cosmo for his audience
   - `content_lesson` — contains a teachable principle about content creation that Cosmo can reference or build on
   - `hook_pattern` — the video uses a strong opening hook that Cosmo can study and adapt
   - `tool_discovery` — introduces or demonstrates an AI tool or software worth Cosmo knowing about
   - `workflow` — describes a repeatable process or system Cosmo or his audience could apply
   - `ai_knowledge` — contains technical AI knowledge worth retaining: how tools work, setup guides, architecture concepts, prompt techniques, model capabilities. Frame for an AI practitioner.
   - `business_knowledge` — contains business strategy, sales, operations, or market knowledge worth retaining. Frame for a business owner or consultant.
   - `knowledge_nugget` — contains general knowledge not specific to AI or business: psychology, economics, history, mental models, behavioral science. Frame as a standalone insight.
   - `news` — time-sensitive industry news or trend with concrete implications
   - `inspiration` — interesting or well-made content that's worth saving, but doesn't fit a specific extract structure (tag only, no extraction)
```

- [ ] **Step 2: Add non-exclusive tagging instruction to STEPS section**

After the tag list, add this guidance (new items 3 and 4, renumber existing items):

```markdown
3. **Tags are non-exclusive.** A single piece of content can and often should produce entries for multiple knowledge files. For example, a video about AI sales funnels might be:
   - `business_knowledge` — framed as a customer journey and sales strategy insight
   - `ai_knowledge` — framed as how to implement the funnel using AI tools
   - `content_lesson` — framed as how to structure posts around funnel stages

   Each tag produces its own extracted object with framing appropriate to that file's purpose. Do not copy-paste the same text into multiple objects — reframe the insight for each context.

4. For each applicable tag (except `inspiration`), extract the relevant structured data as defined in the output format. Include `obsidian_tags` on every extracted object.
```

- [ ] **Step 3: Update OUTPUT FORMAT with new JSON schemas and obsidian_tags**

Replace the entire JSON block in OUTPUT FORMAT (lines 56-98) with:

````markdown
```json
{
  "tags": ["content_lesson", "ai_knowledge", "business_knowledge", "hook_pattern"],
  "summary": "One sentence — what this content is and why it's in the pipeline.",
  "lesson": {
    "title": "Short name for the lesson or principle",
    "principle": "The core insight — framed as a content creation lesson",
    "how_to_apply": "How Cosmo could use this in his content",
    "obsidian_tags": ["content-strategy", "hooks"],
    "source_author": "{author}",
    "source_url": "{source_url}"
  },
  "hooks": [
    {
      "text": "The exact or close-paraphrase opening line from the video",
      "pattern": "authority | contrarian | data | story | cautionary",
      "obsidian_tags": ["topic-keyword"],
      "source_author": "{author}",
      "source_url": "{source_url}"
    }
  ],
  "tool": {
    "name": "Tool name",
    "description": "What it does in one sentence",
    "use_case": "How Cosmo or an SMB operator would actually use this",
    "link": "Product URL if mentioned, otherwise 'None'",
    "obsidian_tags": ["ToolName", "category"],
    "source_author": "{author}",
    "source_url": "{source_url}"
  },
  "idea": {
    "title": "Short punchy title for the content idea — video title energy",
    "angle": "copy_it | remix_it | react_to_it | tool_review | freebie_inspiration",
    "description": "2-3 sentences — what Cosmo would film and why it works for his ICP",
    "obsidian_tags": ["topic-keyword", "format-type"],
    "source_author": "{author}",
    "source_url": "{source_url}"
  },
  "workflow": {
    "title": "Short name for the workflow or system",
    "steps": ["Step 1", "Step 2", "Step 3"],
    "why_it_works": "One sentence — what problem this solves or why it's effective",
    "obsidian_tags": ["workflow-type", "tool-used"],
    "source_author": "{author}",
    "source_url": "{source_url}"
  },
  "ai_knowledge": {
    "title": "Short name for the AI concept or technique",
    "knowledge": "The technical substance — what it is, how it works, key details. Frame for an AI practitioner, not a casual viewer.",
    "key_takeaways": ["Concrete takeaway 1", "Concrete takeaway 2"],
    "obsidian_tags": ["ToolOrConcept", "category"],
    "source_author": "{author}",
    "source_url": "{source_url}"
  },
  "business_knowledge": {
    "title": "Short name for the business insight",
    "insight": "The core business insight — framed for a business owner or consultant. Different from content_lesson: this is about running a business, not creating content.",
    "how_to_apply": "How an SMB owner or consultant would apply this",
    "obsidian_tags": ["business-topic", "industry"],
    "source_author": "{author}",
    "source_url": "{source_url}"
  },
  "knowledge_nugget": {
    "title": "Short name for the insight",
    "knowledge": "The core insight — general knowledge not specific to AI or business. Psychology, economics, history, mental models.",
    "why_it_matters": "Why this matters in practice — what it explains or predicts",
    "obsidian_tags": ["domain", "concept"],
    "source_author": "{author}",
    "source_url": "{source_url}"
  },
  "news_item": {
    "headline": "Short headline for the news item",
    "summary": "What happened, in one or two sentences",
    "why_it_matters": "Why this matters for SMB operators or the AI space",
    "obsidian_tags": ["company-or-topic"],
    "source_author": "{author}",
    "source_url": "{source_url}"
  }
}
```
````

- [ ] **Step 4: Update OUTPUT INSTRUCTIONS**

Replace lines 107-116 with:

```markdown
# OUTPUT INSTRUCTIONS

- Output ONLY the JSON object. No preamble, no explanation, no markdown code fences.
- Be specific — extract actual insights, not vague summaries. If the lesson is "batch your decisions to reduce cognitive load," say that. Don't say "tips for productivity."
- Only include keys for tags you actually applied. A clean JSON object with fewer keys is better than a padded one.
- `source_author` comes from `{author}`. `source_url` comes from `{source_url}`. Fill these in on every extracted object.
- Hook `pattern` must be exactly one of: `authority`, `contrarian`, `data`, `story`, `cautionary`. Choose the best fit.
- A piece of content can have multiple tags. A workflow video that opens with a strong contrarian hook and teaches a principle worth filming is `workflow`, `content_lesson`, `hook_pattern`, and `content_idea` — all at once.
- **Tags are non-exclusive across knowledge types.** The same content can be `ai_knowledge` AND `business_knowledge` AND `content_lesson`. When it is, each extracted object must be framed differently for its target file. Don't duplicate text — rewrite the insight through that file's lens.
- `inspiration` is tag-only. Do not add an `inspiration` key to the output — just include the tag string in the `tags` array.
- The `hooks` field is an array. If the video contains more than one strong hook pattern, extract all of them.
- The JSON must be valid — `json.loads()` must parse it without error.
- **`obsidian_tags`** is required on every extracted object. Include:
  - Tool or product names mentioned (e.g. `Claude`, `Manus`, `Obsidian`, `Apollo`)
  - Topic keywords (e.g. `sales`, `lead-gen`, `content-strategy`, `automation`)
  - Source content type: `short-form`, `podcast`, `long-form`, or `tutorial`
  - Use lowercase-hyphenated format for multi-word tags (e.g. `content-strategy`), but keep proper nouns capitalized (e.g. `Claude`, `Manus`)
  - Aim for 3-6 tags per object. Be specific — `Claude-Code` is better than `AI`.
```

- [ ] **Step 5: Remove `filming_setup` from the idea schema**

In the JSON output example, the `idea` object no longer includes `filming_setup`. It was already not being used in `format_obsidian_entry` — the current format function for `content_idea` only uses `title`, `angle`, `description`, `source_author`, and `source_url`. Remove it from the prompt to avoid wasting tokens.

(This is already done in Step 3's JSON — `filming_setup` is not included in the new `idea` schema.)

- [ ] **Step 6: Commit**

```bash
git add prompts/classify_prompt.md
git commit -m "feat: update classify prompt with new knowledge tags, Obsidian tags, non-exclusive framing"
```

---

### Task 6: Create new Obsidian knowledge files

**Context:** Create the 4 new knowledge files in the Obsidian vault with proper headers matching existing file style.

**Files:**
- Create: `$OBSIDIAN_VAULT_PATH/content/ai-knowledge.md`
- Create: `$OBSIDIAN_VAULT_PATH/content/business-knowledge.md`
- Create: `$OBSIDIAN_VAULT_PATH/content/knowledge-nuggets.md`
- Create: `$OBSIDIAN_VAULT_PATH/content/news.md`

**Obsidian vault path:** `/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault/content/`

- [ ] **Step 1: Create ai-knowledge.md**

```markdown
# AI Knowledge

Technical AI knowledge extracted from saved videos — how tools work, setup guides, architecture concepts, prompt techniques, and model capabilities.

---
```

- [ ] **Step 2: Create business-knowledge.md**

```markdown
# Business Knowledge

Business strategy, sales, operations, and market knowledge extracted from saved videos. Each entry is framed for a business owner or consultant.

---
```

- [ ] **Step 3: Create knowledge-nuggets.md**

```markdown
# Knowledge Nuggets

General knowledge extracted from saved videos — psychology, economics, history, mental models, and behavioral science. Not specific to AI or business.

---
```

- [ ] **Step 4: Create news.md**

```markdown
# News

Timestamped industry news and trends extracted from saved videos.

---
```

- [ ] **Step 5: Commit**

Note: These files are in the Obsidian vault (outside the git repo), so there's nothing to commit here. Verify the files exist:

```bash
ls -la "/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault/content/"
```

Expected: All 4 new files plus the existing 5 files.

---

### Task 7: Update Notion schema with new tag options

**Context:** The Content Tags multi-select in the Links Queue Notion database needs 4 new options: `ai_knowledge`, `business_knowledge`, `knowledge_nugget`, and `news` (news was tag-only before, now it persists).

**Important:** This task uses the Notion MCP tools, NOT Python code. The data source ID is `325a44c6-f32f-8005-884a-000b3031f335`.

**Files:** None (Notion API only)

- [ ] **Step 1: Add new tag options to Content Tags multi-select**

Use Notion MCP `update-data-source` tool to add the new options to the Content Tags property. The existing options are: `content_idea`, `content_lesson`, `hook_pattern`, `tool_discovery`, `workflow`, `news`, `inspiration`.

Add: `ai_knowledge` (blue), `business_knowledge` (purple), `knowledge_nugget` (yellow).

(`news` already exists as an option — no change needed for it.)

- [ ] **Step 2: Verify by querying the database schema**

Use Notion MCP to confirm the new options appear in the Content Tags property.

---

### Task 8: Update CLAUDE.md and ca-help.md with new knowledge files

**Context:** The knowledge file tables in both files need the 4 new entries.

**Files:**
- Modify: `CLAUDE.md`
- Modify: `skills/ca-help.md`

- [ ] **Step 1: Update CLAUDE.md knowledge file table**

In `CLAUDE.md`, find the knowledge file table (under "Knowledge files") and add:

```markdown
| `ai-knowledge.md` | Technical AI knowledge — how tools work, setup guides, architecture |
| `business-knowledge.md` | Business strategy, sales, operations, market knowledge |
| `knowledge-nuggets.md` | General knowledge — psychology, economics, mental models |
| `news.md` | Timestamped industry news and trends |
```

- [ ] **Step 2: Update skills/ca-help.md knowledge file table**

In `skills/ca-help.md`, find the Knowledge Files table and add the same 4 entries:

```markdown
| `ai-knowledge.md` | Technical AI knowledge — how tools work, setup guides, architecture |
| `business-knowledge.md` | Business strategy, sales, operations, market knowledge |
| `knowledge-nuggets.md` | General knowledge — psychology, economics, mental models |
| `news.md` | Timestamped industry news and trends |
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md skills/ca-help.md
git commit -m "docs: add new knowledge files to CLAUDE.md and ca-help.md"
```

---

### Task 9: Validate parse_classifier_output handles new fields

**Context:** The `parse_classifier_output` function validates that `tags` is a list and `summary` is a string. It does NOT validate the inner objects — it passes them through. This is correct behavior since new tag types should work without parser changes. However, we need a test to confirm the full flow works with the new tag types.

**Files:**
- Modify: `tests/test_classifier.py`

- [ ] **Step 1: Write integration-style parse test with new tag types**

```python
def test_parse_output_with_new_knowledge_tags():
    """Full classifier output with new tag types parses correctly."""
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
```

Add `import json` to the top of the test file if not already present.

- [ ] **Step 2: Run all tests**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && python -m pytest tests/test_classifier.py -v`

Expected: ALL tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_classifier.py
git commit -m "test: add integration test for new knowledge tag types"
```

---

### Task 10: End-to-end dry run

**Context:** Run the classifier on a few transcribed (or error) links to verify the full pipeline works with the new prompt, new tags, and new knowledge files.

**Files:** None (runtime validation)

- [ ] **Step 1: Run classifier in dry-run mode**

```bash
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot
python -c "from engines.classifier import classify_all_transcribed; classify_all_transcribed(dry_run=True)"
```

This confirms the code loads without import errors.

- [ ] **Step 2: Classify a single link manually to test new output**

Pick one link from the Notion database that's already classified and re-classify it to verify:
1. Claude outputs the new tag types
2. `obsidian_tags` appear in the output
3. Entries land in the correct knowledge files with `#tag` formatting

To do this, temporarily change one page's status from `classified` back to `transcribed` in Notion, run the classifier, then check the Obsidian files.

- [ ] **Step 3: Verify knowledge file output**

Check the Obsidian vault files for correct formatting:

```bash
tail -20 "/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault/content/ai-knowledge.md"
tail -20 "/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault/content/business-knowledge.md"
```

Expected: Entries with `## Title`, content, `**Tags:** #tag1 #tag2`, `**Source:**`, `**Source URL:**` lines.

- [ ] **Step 4: Run full classification on any remaining transcribed links**

```bash
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot
python engines/classifier.py
```

If there are classification_error links from before:

```bash
python engines/classifier.py --retry-errors
```

---

## Summary of Changes

| What | Files | Lines changed (est.) |
|------|-------|---------------------|
| Obsidian tag rendering helper + all format branches | `engines/classifier.py` | ~80 |
| 3 new knowledge format branches | `engines/classifier.py` | ~50 |
| News format branch | `engines/classifier.py` | ~15 |
| Heading-based dedup | `engines/classifier.py` | ~15 |
| Tag-to-file + tag-to-JSON-key mappings | `engines/classifier.py` | ~10 |
| New tests (tags, new types, dedup, integration) | `tests/test_classifier.py` | ~120 |
| Prompt rewrite (new tags, obsidian_tags, non-exclusive) | `prompts/classify_prompt.md` | ~60 |
| 4 new Obsidian knowledge files | Obsidian vault | 4 files |
| Doc updates | `CLAUDE.md`, `skills/ca-help.md` | ~10 |
| Notion schema | MCP only | — |
