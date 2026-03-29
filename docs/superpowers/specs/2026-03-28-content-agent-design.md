# Content Agent — Design Spec

**Project:** Autom8Lab Content Pipeline Bot → Content Agent Upgrade
**Author:** Cosmo + Claude
**Date:** 2026-03-28
**Status:** Draft

---

## 1. Overview

### What We're Building

Upgrading `content-pipeline-bot` from a capture-and-extract tool into a **Content Agent** — a Claude Code project you can talk to about content, that gets smarter over time from the videos you save.

### The Problem

The current pipeline captures inputs (video links via Telegram, transcripts via TokScript, stored in Notion) but:

1. **Output quality is bad** — captions are generated with zero brand context (17-line prompt)
2. **No pull mechanism** — nothing surfaces content TO you, you dig through the database
3. **Database is overwhelming** — everything sits in one pile with no smart categorization
4. **No compounding intelligence** — each ideation run starts from zero, no learning over time

### The Solution: Three Layers

1. **Smart Intake (Classification)** — auto-classify transcripts into content types, extract insights
2. **Knowledge Memory (Compounding Intelligence)** — rolling knowledge files in Obsidian that get smarter over time
3. **Interactive Skills (Daily Interface)** — morning brief, ideation, research, sparring — all informed by accumulated knowledge

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│  YOU (Claude Code CLI)                                   │
│  Talk, ask questions, run /commands                      │
├─────────────────────────────────────────────────────────┤
│  SKILLS LAYER (markdown prompts)                         │
│  /content-brief  /classify  /ideate  /research  /captions│
│  /content-sparring                                       │
│  Each skill reads from Notion + Obsidian knowledge files │
├─────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE LAYER (Python — mostly existing)         │
│  Telegram bot → Extractors → Orchestrator → Notion API   │
│  + NEW: classifier engine (Python, calls claude CLI)     │
├─────────────────────────────────────────────────────────┤
│  STORAGE                                                 │
│  Notion: Links Queue + Content Ideas (operational DB)    │
│  Obsidian: Knowledge files (compounding intelligence)    │
└─────────────────────────────────────────────────────────┘
```

### Design Principles

- **Skills for creative work, Python for plumbing.** Classification prompts, ideation, sparring = skills (markdown). Notion API calls, file management, orchestration = Python.
- **Obsidian is the knowledge layer, Notion is the operational layer.** Notion tracks status and workflow. Obsidian stores compounding insights the agent reads during conversation.
- **Human-in-the-loop, not autonomous.** The agent classifies and extracts, but you review. It generates ideas, but you pick what to film. Sparring partner, not autopilot.
- **Claude runs locally via CLI, not API.** The classifier calls `claude -m sonnet -p <prompt>` — uses your existing Claude Code subscription.

### Data Flow

```
You send link to Telegram
  → Bot saves to Notion (status: pending)
  → Orchestrator extracts transcript (status: transcribed)
  → Classifier engine runs (status: classified)
       ├── Tags the link in Notion (multi-select Content Tags)
       ├── Writes AI Summary to Notion
       ├── Extracts insights per tag type
       └── Appends to Obsidian knowledge files
  → You interact with the Content Agent
       ├── /content-brief — morning overview
       ├── /ideate — generate ideas (with knowledge context)
       ├── /research — explore a topic
       ├── /captions — generate captions (with brand context)
       ├── /content-sparring — creative discussion
       └── Just talk — conversational, knowledge-informed
```

### Key Research Influences

| Pattern | Stolen From | How We Use It |
|---------|------------|---------------|
| Structured extraction prompts | Fabric (`extract_wisdom`) | Adapt into content-specific classifier prompt |
| Brand-context bootstrapping | archive-dot-com/creator-marketing-skills | Shared `creator_context.md` consumed by all skills |
| Compounding knowledge files | coleam00/second-brain-skills, COG Second Brain | Rolling Obsidian files that skills read as context |
| Parallel subagents | zubair-trabzada/ai-marketing-claude | Fan out for research, fan in results |
| Human-in-the-loop gate | langchain-ai/social-media-agent | AI generates, you approve |
| Obsidian vault access | kepano/obsidian-skills | Official vault read/write skills |

---

## 3. Classification Engine

### Overview

New Python engine (`engines/classifier.py`) that runs after transcription. For each transcribed link, it sends the transcript to Claude (local CLI, Sonnet model) with a Fabric-style extraction prompt. Claude returns tags + extracted insights. Python writes tags to Notion and appends insights to Obsidian.

### Classification Taxonomy

Multi-select field (`Content Tags`) on Links Queue. One video can have multiple tags.

| Tag | Meaning | Extracted To |
|-----|---------|-------------|
| `content_idea` | A topic/take you could recreate or riff on | `idea-backlog.md` |
| `content_lesson` | A framework, principle, or strategy about content creation | `content-principles.md` |
| `hook_pattern` | A specific opening line or hook structure | `hook-bank.md` |
| `tool_discovery` | A tool being demoed or mentioned | `tool-library.md` |
| `workflow` | A process or workflow worth studying | `workflows.md` |
| `news` | Something newsworthy, time-sensitive | Not persisted |
| `inspiration` | Doesn't fit neatly but worth keeping | One-line takeaway only |

### Technical Implementation

```python
# engines/classifier.py (pseudocode)

def classify_link(link):
    prompt = load_prompt("prompts/classify_prompt.md")
    prompt = inject_context(prompt, link.transcript, link.caption)

    # Truncate transcript to ~6000 words if needed (CLI input limit safety)
    # Most short-form transcripts are <500 words; podcasts may hit this cap
    prompt = truncate_transcript_in_prompt(prompt, max_words=6000)

    # Run Claude locally via CLI (Sonnet for speed)
    # Pipe prompt via stdin to avoid ARG_MAX shell limits
    # Timeout prevents hung calls from blocking the orchestrator
    result = subprocess.run(
        ["claude", "-m", "sonnet", "-p", "-"],
        input=prompt, capture_output=True, text=True, timeout=120
    )

    # Parse JSON — strip markdown fences, validate structure
    parsed = parse_classifier_output(result.stdout)
    if parsed is None:
        # Retry once on parse failure
        result = subprocess.run(...)
        parsed = parse_classifier_output(result.stdout)
    if parsed is None:
        # Mark as error, log, continue to next link
        update_notion_status(link.page_id, "classification_error")
        log_error(link.page_id, result.stdout)
        return

    # Write tags + summary to Notion
    update_notion_tags(link.page_id, parsed["tags"])
    update_notion_summary(link.page_id, parsed["summary"])
    update_notion_status(link.page_id, "classified")

    # Append insights to Obsidian knowledge files (direct filesystem write)
    for tag in parsed["tags"]:
        if tag == "content_lesson":
            append_to_obsidian("content-principles.md", parsed["lesson"])
        elif tag == "hook_pattern":
            append_to_obsidian("hook-bank.md", parsed["hooks"])
        elif tag == "tool_discovery":
            append_to_obsidian("tool-library.md", parsed["tool"])
        # ... etc

def parse_classifier_output(raw_output):
    """Strip markdown fences, extract JSON, validate required fields."""
    # Remove ```json ... ``` wrapping if present
    # json.loads() the result
    # Validate: must have "tags" (list) and "summary" (string)
    # Return parsed dict or None on failure
```

### Transcript Length Handling

Short-form transcripts (TikTok, Reels, Shorts) are typically 100-500 words — no issue. Podcast transcripts can be 10,000+ words. The classifier truncates to ~6,000 words (fits comfortably in Sonnet's context with the prompt overhead). For podcasts, the first 6,000 words usually contain the core ideas; the classifier works with what's available.

### Error Handling

If classification fails (CLI error, JSON parse failure, Notion write failure):
1. Retry once on JSON parse failure
2. If still failing, set status to `classification_error` and log the raw output
3. Orchestrator skips `classification_error` links on subsequent runs
4. Can be retried manually via `/classify --retry-errors`

### Extraction Prompt Structure (Fabric-style)

```markdown
# IDENTITY AND PURPOSE

You are a content classification engine for Cosmo, an AI consultant
and content creator. You analyze video transcripts and extract
structured insights.

# CREATOR CONTEXT

{creator_context.md injected here}

# STEPS

1. Read the transcript and original caption carefully
2. Classify into one or more tags: content_idea, content_lesson,
   hook_pattern, tool_discovery, workflow, news, inspiration
3. For each applicable tag, extract the relevant insight
4. Write a one-sentence summary of the video

# OUTPUT FORMAT

Return JSON:
{
  "tags": ["content_lesson", "hook_pattern"],
  "summary": "One sentence summary",
  "lesson": {
    "title": "Short principle name",
    "principle": "The principle in 1-2 sentences",
    "how_to_apply": "How to apply this in content creation",
    "source_author": "@creator",
    "source_url": "..."
  },
  "hooks": [
    {
      "text": "The actual hook text",
      "pattern": "authority|contrarian|data|story|cautionary",
      "source_author": "@creator",
      "source_url": "..."
    }
  ],
  "tool": { ... },
  "idea": { ... },
  "workflow": { ... }
}

# OUTPUT INSTRUCTIONS

- Only include keys for tags that apply
- Be specific — extract the ACTUAL insight, not a summary of the transcript
- For hooks, capture the exact wording used
- For lessons, distill to the transferable principle
- Summary should be useful for scanning, not generic
```

### Orchestrator Integration

```python
# orchestrator.py — add after YouTube extraction step

# Step 4: Classify newly transcribed links
from engines.classifier import classify_all_transcribed
classified_count = classify_all_transcribed(dry_run=dry_run)
print(f"Classification: {classified_count} links classified")
```

### Status Flow Update

```
pending → transcribed → classified → generate_ideas → processed → archived
              ↓              ↘ learning | inspiration | postponed | other
        classification_error
        (retryable via /classify --retry-errors)
```

### Obsidian Write Mechanism

The classifier uses **direct filesystem writes** to the vault path. This is simpler than MCP and works without Obsidian running. The vault path is configured in `.env`:

```
OBSIDIAN_VAULT_PATH=/Users/cosmo/Library/Mobile Documents/iCloud~md~obsidian/Documents/cosmo-vault
```

**iCloud sync risk:** Writing to an iCloud-synced file while it's syncing can cause conflicts. Mitigation: writes are append-only (no overwrites), entries are small, and the classifier runs at a predictable time (evening pipeline). If iCloud conflicts occur in practice, we can switch to writing a staging file locally and syncing via a separate step.

Interactive skills (run during Claude Code sessions) access the vault via `kepano/obsidian-skills` MCP for richer read/search operations.

### Deduplication

Before appending to Obsidian, check if the source URL already exists in the target file (simple grep on `**Source URL:**` lines). If yes, skip. Prevents duplicate entries from re-runs. Known limitation: if the same insight appears from two different source URLs, both get added (which is acceptable — different sources, potentially different framing). This is sufficient for v1 — if files grow large over months, a JSON index file alongside each knowledge file may be needed.

---

## 4. Knowledge Files in Obsidian

### Location

```
cosmo-vault/content/
├── content-principles.md    ← Content creation lessons
├── hook-bank.md             ← Opening lines by pattern type
├── tool-library.md          ← Tools discovered from videos
├── idea-backlog.md          ← Content ideas from saved videos
└── workflows.md             ← Processes and workflows
```

### Entry Formats

**content-principles.md:**
```markdown
## Hook-Payoff Gap
The best hooks open a question the viewer needs closed. The wider
the gap, the longer they watch.

**How to apply:** Open with a claim that sounds wrong or surprising.
Don't explain immediately — let the gap sit for 2-3 seconds.

**Source:** @creatorname · 2026-03-28
**Source URL:** https://tiktok.com/...
```

**hook-bank.md:**
```markdown
### Authority
- "I've reviewed 200 TikTok accounts this year. Here's what the
  top 1% do differently." — @creator · 2026-03-28

### Contrarian
- "Stop posting every day. It's killing your account." — @creator · 2026-03-26
```

**tool-library.md:**
```markdown
## Descript
Video editing tool with AI-powered transcript editing. Edit video
by editing text.

**Use case for me:** Could speed up short-form editing. Worth testing
for TikTok batch production.
**Mentioned by:** @creator · 2026-03-28
**Link:** https://descript.com
```

**idea-backlog.md:**
```markdown
## "Most Automation Projects Fail Before They Start"
Angle: Pattern Break — challenge the assumption that AI tools are
the bottleneck. The real bottleneck is nobody wrote down the process.

**Filming setup:** talking_head
**Source:** @creator's video about failed AI implementations · 2026-03-28
**Source URL:** https://tiktok.com/...
```

**workflows.md:**
```markdown
## Batch Filming Workflow (3 Videos in 1 Hour)
1. Prep all 3 scripts the night before
2. Set up camera once, don't move it
3. Film all 3 back-to-back, change shirt between each
4. Edit in batch — same style, same captions template

**Why it works:** Eliminates setup time which is the biggest time sink.
**Source:** @creator · 2026-03-28
```

### How Knowledge Files Are Consumed

| Context | Files Read |
|---------|-----------|
| `/content-brief` | All files (recent entries only) |
| `/ideate` | `content-principles.md`, `hook-bank.md`, `idea-backlog.md` |
| `/captions` | `content-principles.md`, `hook-bank.md` |
| `/content-sparring` | All files |
| Conversational mode | CLAUDE.md points to all files, read on demand |

### Context Budget

As knowledge files grow over months, they will eventually get large. Design constraint: skills that read knowledge files should read **recent entries only** (last 30 days or last N entries) rather than the full file. The entry format includes dates, making it easy to filter. If a file exceeds ~500 lines, older entries can be archived to a separate file (e.g., `content-principles-archive.md`). This does not need solving now but the date-stamped entry format ensures it's possible later.

---

## 5. Skills Layer

### Skill Execution Model

Skills are markdown prompt files that guide Claude's behavior during a conversation. They do NOT execute code themselves. When a skill needs data from Notion or needs to write to Notion, it instructs Claude to use one of two mechanisms:

1. **Notion MCP** — Claude uses the Notion MCP server (already connected) for database queries and page updates. Skills include the database IDs and query instructions.
2. **Python helper scripts** — For complex data gathering, a skill instructs Claude to run a Python script that returns structured data. Example: `python engines/ideation.py --list` to get queued links.

This means: **skills are the brain (what to do, how to think), Python scripts are the hands (fetch data, write to APIs).**

### Skill Files

All skills live in `skills/` and follow the standard SKILL.md format.

#### `/content-brief`

**File:** `skills/content-brief.md`

**Execution pattern:** Skill instructs Claude to query Notion via MCP for link counts and idea status, then read Obsidian knowledge files for recent entries, then synthesize.

**What it produces:**
1. "You saved X videos this week. Y classified, Z waiting."
2. 3 content ideas ranked by score + recency
3. 1 principle you collected this week (from content-principles.md)
4. 1 tool worth mentioning in content (from tool-library.md)
5. Filming queue status

#### `/classify`

**File:** `skills/classify.md`

**Execution pattern:** Skill instructs Claude to run `python engines/classifier.py` which handles the batch classification. Shows results, lets you adjust tags interactively via Notion MCP. Supports `python engines/classifier.py --retry-errors` to re-attempt previously failed classifications.

#### `/ideate [optional topic or link]`

**File:** `skills/ideate.md`

**Execution pattern:** Skill instructs Claude to run `python engines/ideation.py --list` to get queued links, then reads knowledge files for context, then runs the 4-skill ideation pipeline (which is conversational — Claude follows the pipeline instructions from `prompts/ideation_pipeline.md`), then saves results via `engines/ideation.py --save`.

**Key difference from current ideation:** Knowledge files (`content-principles.md`, `hook-bank.md`) are injected as context before the pipeline runs. Ideas and hooks are informed by accumulated lessons.

#### `/research [topic]`

**File:** `skills/research.md`

**Execution pattern:** Conversational skill. Claude uses its built-in web search and Agent tool for research. No subagent framework needed — Claude Code already supports this natively. Optionally saves findings to knowledge files via direct file write.

#### `/captions`

**File:** `skills/captions.md`

**Execution pattern:** Skill instructs Claude to run `python engines/captions.py --list` to get filmed ideas, then reads `creator_context.md` + knowledge files for brand context, then generates captions conversationally, then saves via `engines/captions.py --save`.

**Key difference from current captions:** Full brand context + knowledge file context injected. The existing `captions.py` stays as the Notion query/save layer. The skill replaces the thin `prompts/captions.txt` as the prompt that guides caption generation.

#### `/content-sparring`

**File:** `skills/content-sparring.md`

**Execution pattern:** Pure conversational skill. Loads `creator_context.md` + all knowledge files as context. No Python scripts involved. Claude reads the files and enters creative discussion mode.
- Pushes back on generic ideas, references collected principles and hooks
- No auto-save — conversational only, you decide what to act on

### CLAUDE.md

The project's `CLAUDE.md` ties everything together:

```markdown
# Content Agent — Cosmo's Content Pipeline

## Who You Are
You are Cosmo's content sparring partner. You have access to his
content knowledge base, saved video transcripts, and brand guidelines.
You help him make better content by using what he's already collected.

## Context Files (read when relevant)
- prompts/creator_context.md — brand, voice, ICP, pillars
- [vault]/content/content-principles.md — collected lessons
- [vault]/content/hook-bank.md — collected hooks by pattern type
- [vault]/content/tool-library.md — discovered tools
- [vault]/content/idea-backlog.md — content ideas from saved videos
- [vault]/content/workflows.md — processes worth copying

## Slash Commands
/content-brief, /classify, /ideate, /research, /captions, /content-sparring

## Behavior
- Lead with what's actionable
- Reference specific entries from knowledge files
- Push back on weak ideas — sparring partner, not yes-man
- Output is the goal — bias toward "film this" not "think about this"
- Apply operating principles: volume before optimization, challenge
  unrealistic timelines, don't let him hide
```

---

## 6. Changes to Existing Code

### New Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project brain — context, commands, behavior |
| `engines/classifier.py` | Classification engine |
| `prompts/classify_prompt.md` | Fabric-style extraction prompt |
| `skills/content-brief.md` | Morning brief skill |
| `skills/classify.md` | Classification skill |
| `skills/ideate.md` | Ideation skill |
| `skills/research.md` | Research skill |
| `skills/captions.md` | Upgraded captions skill |
| `skills/content-sparring.md` | Creative discussion skill |

### Modified Files

| File | Changes |
|------|---------|
| `orchestrator.py` | Add classifier step after extraction |
| `prompts/captions.txt` | Rewrite with full brand context (consumed by `skills/captions.md`) |

Note: `engines/captions.py` stays as-is — it handles Notion queries and saves. The skill (`skills/captions.md`) replaces the thin prompt with knowledge-aware instructions. No Python changes needed for captions.

### Notion Changes

| Change | Details |
|--------|---------|
| New field: `Content Tags` | Multi-select on Links Queue (`content_idea`, `content_lesson`, `hook_pattern`, `tool_discovery`, `workflow`, `news`, `inspiration`) |
| New field: `AI Summary` | Rich text on Links Queue |
| New status: `classified` | Between `transcribed` and `generate_ideas` |
| New view: `Classified` | Filtered by status=classified, grouped by Content Tags |

### Untouched

- `bot/main.py` — Telegram bot
- `extractors/*` — All three extractors
- `engines/ideation.py` — Python engine (skills call into it)
- `prompts/creator_context.md` and brand files
- Content Ideas DB structure

---

## 7. Obsidian Setup (Separate Workstream)

Handle in a separate Claude Code session before or in parallel:

1. **Install `kepano/obsidian-skills`** (github.com/kepano/obsidian-skills) — official vault read/write skills for AI agents
2. **Create `cosmo-vault/content/` folder** with knowledge files seeded with headers
3. **Test write access** from Claude Code CLI to iCloud-synced vault path
4. **Optional:** Install `obsidian-smart-connections` for semantic search
5. **Optional:** Review `COG-second-brain` (github.com/huytieu/COG-second-brain) and `second-brain-skills` (github.com/coleam00/second-brain-skills) for vault structure inspiration

**Fallback:** If Obsidian isn't ready, the `append_to_obsidian()` function reads the vault path from `.env` (`OBSIDIAN_VAULT_PATH`). If the env var is unset or the path doesn't exist, it falls back to writing knowledge files locally in `content-pipeline-bot/knowledge/` until vault access is configured.

---

## 8. Research References

Projects studied during design:

**Core Influences:**
- [danielmiessler/fabric](https://github.com/danielmiessler/fabric) — Extraction prompt patterns (extract_wisdom)
- [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) — Official Obsidian vault access for AI agents
- [huytieu/COG-second-brain](https://github.com/huytieu/COG-second-brain) — Claude Code + Obsidian second brain architecture
- [coleam00/second-brain-skills](https://github.com/coleam00/second-brain-skills) — Compounding knowledge files pattern
- [archive-dot-com/creator-marketing-skills](https://github.com/archive-dot-com/creator-marketing-skills) — Brand-context bootstrapping

**Claude Code Ecosystem:**
- [anthropics/skills](https://github.com/anthropics/skills) — Official skill format reference
- [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python) — Agent SDK (future migration path)
- [anthropics/claude-agent-sdk-demos](https://github.com/anthropics/claude-agent-sdk-demos) — Research Agent demo
- [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) — Content production/strategy/humanizer skill decomposition
- [zubair-trabzada/ai-marketing-claude](https://github.com/zubair-trabzada/ai-marketing-claude) — Parallel subagent pattern
- [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) — Agent harness architecture

**Content Workflow References:**
- [langchain-ai/social-media-agent](https://github.com/langchain-ai/social-media-agent) — Human-in-the-loop content pipeline
- [lucaswalter/n8n-ai-automations](https://github.com/lucaswalter/n8n-ai-automations) — Content repurposing factory
- [sirlifehacker/social-story-scraper](https://github.com/sirlifehacker/social-story-scraper) — Three-database Notion architecture
- [langchain-ai/content-writer](https://github.com/langchain-ai/content-writer) — Learning from feedback (SharedValue pattern)

**Knowledge Management:**
- [khoj-ai/khoj](https://github.com/khoj-ai/khoj) — Self-hosted AI second brain with Obsidian integration
- [mem0ai/mem0](https://github.com/mem0ai/mem0) — Universal memory layer for AI agents
- [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) — Session memory persistence for Claude Code
- [letta-ai/letta-obsidian](https://github.com/letta-ai/letta-obsidian) — Stateful AI agent in Obsidian
- [doobidoo/mcp-memory-service](https://github.com/doobidoo/mcp-memory-service) — Persistent memory via MCP
