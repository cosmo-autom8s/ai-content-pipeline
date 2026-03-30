---
name: ca-brief
description: Morning content brief — pipeline status, top ideas, recent knowledge
---

You are generating Cosmo's morning content brief. Be fast, scannable, and action-oriented. Lead with what to DO today.

## Step 1 — Query Links Queue (Notion MCP)

Query the Links Queue database using the Notion MCP tool.
- Database ID: `325a44c6f32f8086a1e4e1b10d6e6de9` (env var: `$NOTION_LINKS_DB_ID`)
- Filter: entries created in the past 7 days
- Count results grouped by status: `transcribed`, `classified`, `generate_ideas`

If the MCP query fails, note it and continue with what's available.

## Step 2 — Query Content Ideas DB (Notion MCP)

Query the Content Ideas database using the Notion MCP tool.
- Database ID: `325a44c6f32f80fb9ff3f0760c28fb48` (env var: `$NOTION_IDEAS_DB_ID`)
- Count ideas by status: `new`, `queued`, `filming_today`, `filmed`
- Retrieve top 3 ideas sorted by score (descending) — only if a score field exists
- Note the title, status, and score for each top idea

If the MCP query fails, note it and continue.

## Step 3 — Read Knowledge Files

Read the last 5 entries (or last ~100 lines) of each knowledge file. Try the Obsidian vault path first, fall back to local `knowledge/` directory.

Files to read (in order of priority):
1. `$OBSIDIAN_VAULT_PATH/content/content-principles.md` → fallback: `knowledge/content-principles.md`
2. `$OBSIDIAN_VAULT_PATH/content/hook-bank.md` → fallback: `knowledge/hook-bank.md`
3. `$OBSIDIAN_VAULT_PATH/content/tool-library.md` → fallback: `knowledge/tool-library.md`
4. `$OBSIDIAN_VAULT_PATH/content/idea-backlog.md` → fallback: `knowledge/idea-backlog.md`

Skip silently if a file doesn't exist — do not error out.

## Step 4 — Synthesize the Brief

Output the brief in this exact structure. No preamble, no "here's your brief", just the content.

---

# Content Brief — [Today's Date]

## Pipeline Status
- **Saved this week:** X links total (Y transcribed, Z classified, N awaiting triage)
- **Ideas in queue:** X new, Y queued, Z filming today, N filmed

## Top 3 Ideas to Film
Pulled from Content Ideas DB, sorted by score. If no score exists, surface the 3 most recent `queued` ideas.

1. **[Idea Title]** — Score: X | Status: queued
2. **[Idea Title]** — Score: X | Status: queued
3. **[Idea Title]** — Score: X | Status: new

## Filming Queue (Do This Today)
List any ideas with status `filming_today`. If none, recommend the top-scored idea from the list above with a one-line reason why now is the right time.

## This Week's Principle
One standout lesson or belief from `content-principles.md` — pick the most recent entry or the one most relevant to the top idea above. One sentence, direct.

## Tool Worth Mentioning
From `tool-library.md` — surface one recently added tool if there's a recency signal. Otherwise pick one that aligns with the top idea. Name + one sentence on why it's relevant right now.

---

Format rules:
- No bullet point walls — keep each section tight
- Skip any section if the data genuinely isn't available (note it in one line)
- Total brief should be readable in under 2 minutes
