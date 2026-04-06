---
name: ca-ideate
description: Generate content ideas from queued links or a topic — powered by knowledge files
---

Generate content ideas for Cosmo's personal brand using the full ideation pipeline, enriched with accumulated knowledge from the vault and idea backlog.

## Steps

### 1. Determine the Source

Check if the user provided a topic as an argument (e.g., `/ca-ideate AI agents are overhyped`):

- **Topic provided:** Ideate freely on that topic — skip the link fetch and use the topic as the source material.
- **No topic:** Run `python engines/ideation.py --list` to retrieve queued links tagged `generate_ideas`. Show the user the list and confirm which to process (default: all).

### 2. Load Knowledge Files

Read the following files for context — these inject accumulated learning into the pipeline so ideas reflect patterns Cosmo has discovered over time, not just the raw source material:

- `$OBSIDIAN_VAULT_PATH/content/content-principles.md` — if the env var is not set or the file doesn't exist, fall back to `knowledge/content-principles.md`
- `$OBSIDIAN_VAULT_PATH/content/hook-bank.md` — fall back to `knowledge/hook-bank.md`
- `$OBSIDIAN_VAULT_PATH/content/idea-backlog.md` — fall back to `knowledge/idea-backlog.md` (skip gracefully if missing)

### 3. Load Brand Context

Read `prompts/creator_context.md` for brand voice, ICP, content pillars, founder identity, and language rules.

Read `prompts/ideation_pipeline.md` for the full 4-step pipeline instructions.

### 4. Run the Ideation Pipeline

Follow the 4-step pipeline from `prompts/ideation_pipeline.md` exactly:

1. **Idea Gen** — Generate 5 content ideas per source (or for the provided topic). Apply knowledge file patterns: hook structures from the hook bank, principles from content-principles, gaps from the idea backlog.
2. **Hooks** — Generate 5 viral hooks per idea, optimized for short-form video.
3. **Creative Director** — Score, rank, kill weak ideas, flag the top pick.
4. **De-AI-ify** — Strip hedging, buzzwords, and vendor language. Apply Cosmo's voice.

**Key difference from raw ideation:** Knowledge files are injected as active context. Hook bank patterns inform hook generation. Content principles constrain what passes the quality filter. Idea backlog prevents duplicates and reveals what's already been explored.

### 5. Present Ideas for Review

Display each idea in a readable format with its score, hooks, and the top pick flagged. Ask: "Which of these do you want to save?"

### 6. Save Approved Ideas

For each approved idea, save it using one of:
- `python engines/ideation.py --save '{"page_id":"<SOURCE_PAGE_ID>","url":"<SOURCE_URL>"}' '[...]'`
- Notion MCP — create a new page in the Ideas database with all fields from the pipeline output format

Confirm how many ideas were saved and offer to queue them for filming.
