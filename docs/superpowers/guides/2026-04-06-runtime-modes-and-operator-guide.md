# Runtime Modes And Operator Guide

This repo supports three real operating modes. Choose based on cost, autonomy, and which agent you want to drive the session.

## 1. Claude Automated

Use this when you want unattended runs, including cron jobs.

Setup:

```bash
export AGENT_RUNTIME=claude
export EXTRACTOR_BACKEND=claude_cli
```

Run:

```bash
python orchestrator.py
```

What happens:

1. CSV fallback files are parsed first.
2. Pending Spotify podcast links are converted to YouTube.
3. Pending supported video links are extracted through Claude CLI + TokScript MCP.
4. Transcribed links are classified through OpenRouter.
5. Knowledge entries are appended into Obsidian.

Caveat:

- This is the most automated mode today.
- It spends Anthropic credits on extraction.

## 2. Hybrid

Use this when you want unattended runs but lower spend.

Setup:

```bash
export AGENT_RUNTIME=claude
export EXTRACTOR_BACKEND=claude_cli
```

Run:

```bash
python orchestrator.py
```

What changes from Claude Automated:

- Extraction still uses Claude.
- Classification uses OpenRouter, so you can choose cheaper or free models.

Caveat:

- Free OpenRouter models can be slow, rate-limited, or timeout under load.

## 3. Codex Session-Native

Use this when you want to operate the pipeline locally from a Codex session.

Setup:

```bash
export AGENT_RUNTIME=codex
export EXTRACTOR_BACKEND=agent_prompt
```

Run:

```bash
python orchestrator.py
```

What happens:

1. CSV fallback files are parsed first.
2. Pending Spotify podcast links are converted to YouTube.
3. Supported pending extraction work is turned into queued extraction jobs.
4. Codex processes those jobs through MCP tools.
5. Classification can run through OpenRouter or directly in-session.

## Codex Extraction Workflow

Queue work:

```bash
AGENT_RUNTIME=codex EXTRACTOR_BACKEND=agent_prompt python orchestrator.py
```

Inspect work:

```bash
python extractors/extraction_jobs.py
python extractors/extraction_jobs.py --next
python extractors/extraction_jobs.py --id JOB_ID
```

Claim and process:

```bash
python extractors/extraction_jobs.py --claim JOB_ID --worker codex
```

Then, in the Codex session:

1. read the job payload and prompt path
2. fetch transcripts with TokScript MCP
3. update Notion rows
4. write agent output to a local text file
5. complete the job

Complete or fail:

```bash
python extractors/extraction_jobs.py --complete JOB_ID --output-file /path/to/output.txt
python extractors/extraction_jobs.py --fail JOB_ID --error "reason"
python extractors/extraction_jobs.py --release JOB_ID
```

Clean up stale jobs:

```bash
python extractors/extraction_jobs.py --stale
python extractors/extraction_jobs.py --prune-stale
```

`--stale` compares queued jobs to the live pending Notion queue. If all URLs in a queued job are no longer pending, that job is stale. `--prune-stale` archives it into `csv_inbox/extraction_jobs/stale/`.

## Manual In-Session Classification

This is useful when OpenRouter is slow or you want direct agent judgment.

Workflow:

1. query a `transcribed` link from Notion
2. classify it into the shared tag schema:
   - `content_lesson`
   - `hook_pattern`
   - `tool_discovery`
   - `content_idea`
   - `workflow`
   - `ai_knowledge`
   - `business_knowledge`
   - `knowledge_nugget`
   - `news`
   - `inspiration`
3. write `Content Tags`, `AI Summary`, and `Status=classified` back to Notion
4. append extracted knowledge into the matching Obsidian files

This path is session-native and cheap in practice, but it is not the unattended batch path.

## What The Orchestrator Processes

Supported automated categories:

- `youtube.com/watch`
- `youtu.be`
- `youtube.com/shorts`
- `instagram.com/reel`
- `tiktok.com`
- Spotify podcast URLs that can be converted to YouTube first

Stored but not auto-transcribed yet:

- `carousel`
- `linkedin`
- `reddit`
- `x_post`

These remaining links stay `pending` by design.
