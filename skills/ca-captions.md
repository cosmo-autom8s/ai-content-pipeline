---
name: ca-captions
description: Generate platform captions for filmed content ideas
---

Generate platform-specific captions for ideas that have been filmed and are ready for posting.

## Steps

### 1. Fetch Filmed Ideas

Run `python engines/captions.py --list` to get ideas with status `filmed` (or equivalent status indicating filming is complete).

If no filmed ideas are returned, tell the user: "No filmed ideas found in the queue. You may want to check the Notion board directly to verify statuses — sometimes filmed ideas need their status updated first." Offer to open the Notion view via MCP if they'd like.

Otherwise, display the list and ask: "Generate captions for all of these, or pick specific ones?"

### 2. Load Brand Context

Read `prompts/creator_context.md` for brand voice, ICP, language rules, content pillars, and founder identity.

### 3. Load Caption Prompt

Read `prompts/captions.txt` — this contains the full caption generation instructions, platform rules, hook patterns, language rules, and output format.

### 4. Load Knowledge Files

Read the following for latest context to keep captions sharp and current:

- `$OBSIDIAN_VAULT_PATH/content/content-principles.md` — fall back to `knowledge/content-principles.md`
- `$OBSIDIAN_VAULT_PATH/content/hook-bank.md` — fall back to `knowledge/hook-bank.md` (skip gracefully if missing)

Use hook bank patterns to inform hook selection. Use content principles to filter out anything that doesn't meet the bar.

### 5. Generate Captions

For each filmed idea, generate captions across all four platforms following the instructions in `prompts/captions.txt`:

- TikTok
- Instagram
- YouTube Shorts
- LinkedIn

Apply the hook-first principle to every caption. Pass both brand filters before finalizing. Use SMB owner language, not vendor language.

### 6. Present for Review

Display captions per idea, grouped by platform. Format them clearly so Cosmo can read each one and approve or request changes.

Ask: "Which captions are good to save? Any you want me to revise?"

Make requested revisions before saving.

### 7. Save Approved Captions

For each approved set, update the idea's Notion page via Notion MCP or:

- `python engines/captions.py --save <PAGE_ID> '{"caption_tiktok":"...","caption_instagram":"...","caption_youtube":"...","caption_linkedin":"..."}'`

Update fields:
- `caption_tiktok`
- `caption_instagram`
- `caption_youtube`
- `caption_linkedin`

Confirm how many ideas were updated and offer to mark them as `captioned` if they're fully done.
