# Autom8Lab Content Engine

**Version:** 2.4.0
**Last updated:** 2026-04-06
**Phase:** 2 — Content Agent + Dual-Agent Runtime

Turn raw video links into classified knowledge, actionable content ideas, and platform-ready captions. This repo now supports three operating modes: fully automated Claude runs, cheaper OpenRouter-assisted hybrid runs, and Codex-native session runs that use MCP tools directly.

This is the core idea: the business logic lives in the repo, not inside one agent. Claude and Codex are both operators over the same pipeline state in Notion, the same knowledge files in Obsidian, and the same Python orchestration layer.

---

## How It Works

```
You (throughout the day)
  |  Send link to Telegram bot
  v
Telegram Bot ──> Text file (backup) + Notion Links Queue*
                  (* TikToks & Reels: text file only — Notion row via TokScript)
  |
  v
Evening Pipeline (orchestrator.py)
  |
  ├── Extraction runtime ─ extracts transcripts for supported video links
  │                         via Claude CLI + TokScript MCP
  │                         or via Codex extraction jobs + TokScript MCP
  ├── Spotify Converter ── finds YouTube version of Spotify podcasts
  ├── TokScript CSV ────── fallback: parses CSV exports if MCP unavailable
  └── Classifier v2 ────── auto-tags with non-exclusive knowledge tags + writes to Obsidian
  |                         via OpenRouter API
  |                         or in-session via Codex / Claude
  |                         (ai_knowledge, business_knowledge, content_lesson, hook_pattern,
  |                          tool_discovery, content_idea, workflow, knowledge_nugget, news)
  v
Obsidian Knowledge Files (auto-populated, deduplicated)
  |  ai-knowledge.md, business-knowledge.md, content-principles.md,
  |  hook-bank.md, tool-library.md, idea-backlog.md, workflows.md,
  |  knowledge-nuggets.md, news.md
  v
Links Queue (status: classified)
  |
  v  You review & tag: generate_ideas / learning / inspiration / postponed / other
  |
Links Queue (status: generate_ideas)
  |
  v
Ideation Pipeline (4-skill process via Claude Code)
  |  content-idea-generator → viral-hook-creator → creative-director → de-ai-ify
  |  5 ideas per video, 5 hooks per idea, scored and ranked
  v
Content Ideas DB (Notion) ──> Dashboard (localhost:8088)
  |
  v  You film it, then...
  |
Caption Generator (interactive via Claude Code)
  |  Platform-specific captions for TikTok, IG, YouTube, LinkedIn
  v
You post it
```

---

## Runtime Modes

You can run the same system in three ways:

| Mode | Best for | What runs where | Cost profile | Caveats |
|------|----------|-----------------|--------------|---------|
| Claude Automated | Cron jobs, unattended nightly runs | Python orchestrator + Claude CLI subprocess + TokScript MCP | Spends Anthropic credits | Most automated today, but extraction uses Claude credits |
| Hybrid | Cheaper unattended classification | Claude for extraction, OpenRouter for classifier | Cheaper than full Claude, can be near-free for classification | Free OpenRouter models can be slow, rate-limited, or timeout |
| Codex Session-Native | Manual operator runs in ChatGPT Codex | Python for queueing + Codex MCP for extraction + optional in-session classification | Spends OpenAI credits (much cheaper) instead of Anthropic | Not fully unattended yet; Codex extraction runs through queued jobs in-session |

Recommended use:

- Use `Claude Automated` when you want the nightly pipeline to run unattended.
- Use `Hybrid` when you want to keep automation but reduce Anthropic spend.
- Use `Codex Session-Native` when you want the best bang for your buck and do not mind pressing a few buttons to run it manually.

Reference guide: [2026-04-06-runtime-modes-and-operator-guide.md](docs/superpowers/guides/2026-04-06-runtime-modes-and-operator-guide.md)

---

## Content Agent

The Content Agent is an upgrade from a capture-and-process tool into a conversational content sparring partner. Instead of just running scripts, you can open a Claude or Codex session and talk through ideas, get a morning brief, run classification interactively, or spar on hooks and angles — all grounded in your Notion backlog, brand principles, and 9 knowledge files. Every classified video automatically enriches the knowledge files, making future briefs, ideation, and sparring sessions more informed.

`/ca-*` slash commands are Claude Code skills. Codex can perform the same underlying workflows, but not through the same slash-command interface.

### `/ca-*` Commands

| Command | What it does |
|---------|-------------|
| `/ca-help` | Show all Content Agent commands and usage tips |
| `/ca-brief` | Morning content brief — pipeline status, top ideas, one principle, one tool |
| `/ca-extract` | Extract transcripts from pending links via TokScript MCP (all platforms) |
| `/ca-classify` | Run the classifier on transcribed links — auto-tag and extract to knowledge files |
| `/ca-ideate` | Generate content ideas from queued links or a freeform topic, informed by knowledge files |
| `/ca-research` | Research a topic for content angles — search web, save findings to knowledge files |
| `/ca-captions` | Generate platform-ready captions after filming, using your voice and brand principles |
| `/ca-sparring` | Creative discussion mode — push back on weak ideas, reference your knowledge and principles |

### Daily Workflow

| When | What | How |
|------|------|-----|
| Morning | Get a content brief | `/ca-brief` in Claude Code, or ask Codex to summarize pipeline state |
| During the day | Save links | Send to Telegram bot |
| During the day | Freeform ideation or hook refinement | `/ca-sparring` or `/ca-research` in Claude Code, or equivalent Codex session prompts |
| Evening | Run pipeline | `python orchestrator.py` for unattended or hybrid runs, or queue/extract in Codex session |
| Evening | Triage links | In Notion, set each classified link to `generate_ideas`, `learning`, `inspiration`, `postponed`, or `other` |
| Evening | Generate ideas | `python engines/ideation.py`, `/ca-ideate`, or a Codex-led save flow using the same script |
| Evening | Review ideas | Dashboard at `localhost:8088` — filter, sort, score, review |
| After filming | Generate captions | `/ca-captions` in Claude Code or `python engines/captions.py --save ...` from either agent |
| After filming | Post content | Copy captions from Notion, post manually |

---

## Classifier v2 — Knowledge Extraction

The classifier reads each transcribed video and produces structured extractions across 9 non-exclusive tag types. "Non-exclusive" means a single video about AI sales funnels can simultaneously produce:

- **ai_knowledge** → technical implementation framed for a practitioner
- **business_knowledge** → strategy framed for a business owner
- **content_lesson** → principle framed for a content creator

Each extraction is written to its own Obsidian knowledge file with `#tags` for cross-referencing.

### Tag Types

| Tag | JSON Key | Obsidian File | What it captures |
|-----|----------|---------------|-----------------|
| `content_lesson` | `lesson` | `content-principles.md` | Teachable content creation principles |
| `hook_pattern` | `hooks` | `hook-bank.md` | Strong opening hooks with named patterns |
| `tool_discovery` | `tool` | `tool-library.md` | AI tools and software worth knowing |
| `content_idea` | `idea` | `idea-backlog.md` | Filmable content ideas with angles |
| `workflow` | `workflow` | `workflows.md` | Repeatable processes and systems |
| `ai_knowledge` | `ai_knowledge` | `ai-knowledge.md` | Technical AI knowledge for practitioners |
| `business_knowledge` | `business_knowledge` | `business-knowledge.md` | Business strategy and operations insights |
| `knowledge_nugget` | `knowledge_nugget` | `knowledge-nuggets.md` | Psychology, economics, mental models |
| `news` | `news_item` | `news.md` | Time-sensitive industry news (date-stamped) |
| `inspiration` | — | — | Tag-only, no extraction |

### Deduplication

- **URL-based:** Same source URL won't be written twice to any file
- **Heading-based:** Same `## Tool Name` heading won't be duplicated (prevents duplicate tool entries from different sources)

### Obsidian Tags

Every extracted entry includes `#tags` for Obsidian cross-referencing:
- Tool/product names: `#Claude`, `#Manus`, `#Descript`
- Topic keywords: `#sales`, `#lead-gen`, `#content-strategy`
- Source format: `#short-form`, `#podcast`, `#long-form`

---

## Knowledge Files

Knowledge files are the Content Agent's long-term memory. They're auto-populated by the classifier and read by `/ca-brief`, `/ca-ideate`, `/ca-sparring`, and `/ca-research` to ground responses in accumulated insights rather than generic best practices.

**Primary location:** `$OBSIDIAN_VAULT_PATH/content/` (Obsidian vault, synced across devices)
**Fallback location:** `knowledge/` (local dir in this repo)

| File | What it contains | Populated by |
|------|-----------------|--------------|
| `content-principles.md` | Content creation lessons — what works, what doesn't | Classifier (`content_lesson`) |
| `hook-bank.md` | Proven hook structures with named patterns | Classifier (`hook_pattern`) |
| `tool-library.md` | AI and ops tools with use cases and links | Classifier (`tool_discovery`) |
| `idea-backlog.md` | Filmable content ideas with angles | Classifier (`content_idea`) |
| `workflows.md` | Repeatable processes and systems | Classifier (`workflow`) |
| `ai-knowledge.md` | Technical AI knowledge for practitioners | Classifier (`ai_knowledge`) |
| `business-knowledge.md` | Business strategy, sales, ops insights | Classifier (`business_knowledge`) |
| `knowledge-nuggets.md` | Psychology, economics, mental models | Classifier (`knowledge_nugget`) |
| `news.md` | Time-sensitive industry news (date-stamped) | Classifier (`news`) |

---

## Dashboard

A React + FastAPI dashboard for reviewing content ideas at `localhost:8088`.

- Filter by status, format, and score
- Sort by score, date, or filming priority
- Search across idea titles and descriptions
- Slide-out detail panel with hooks, scoring, and captions

Start with: `./run.sh` (builds frontend + starts FastAPI server)

---

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r api/requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your tokens:
#   TELEGRAM_BOT_TOKEN
#   TELEGRAM_CHAT_ID
#   NOTION_API_KEY
#   NOTION_LINKS_DB_ID
#   NOTION_IDEAS_DB_ID
#   OBSIDIAN_VAULT_PATH  (path to your Obsidian vault)
#   OPENROUTER_API_KEY   (for classifier — uses free Qwen model)
#   CLASSIFIER_MODEL     (default: qwen/qwen3.6-plus:free)
#   CLASSIFIER_DELAY     (seconds between API calls, default: 5)
#   AGENT_RUNTIME        (claude or codex)
#   EXTRACTOR_BACKEND    (claude_cli or agent_prompt)
```

### 3. Validate the environment

```bash
python validate_env.py
python validate_env.py --skip-network
```

`validate_env.py` checks `.env`, the Obsidian vault path, Notion API access, and OpenRouter auth. TokScript/Notion MCP access must be validated from the active agent session.

Recommended smoke test before a real run:

```bash
python validate_env.py
python orchestrator.py --status
python orchestrator.py --dry-run
python engines/classifier.py --dry-run
```

### 4. Run the Telegram bot

```bash
python bot/main.py
```

### 5. Choose a runtime mode

Claude automated:

```bash
export AGENT_RUNTIME=claude
export EXTRACTOR_BACKEND=claude_cli
```

Hybrid:

```bash
export AGENT_RUNTIME=claude
export EXTRACTOR_BACKEND=claude_cli
# classifier still uses OpenRouter via OPENROUTER_API_KEY
```

Codex session-native:

```bash
export AGENT_RUNTIME=codex
export EXTRACTOR_BACKEND=agent_prompt
```

### 6. Run the evening pipeline

```bash
python orchestrator.py           # Full pipeline: CSV inbox + Spotify conversion + extraction + classification
python orchestrator.py --dry-run # Preview what would be processed
python orchestrator.py --status  # Show current queue counts
```

### 7. Run the dashboard

```bash
./run.sh                         # Builds frontend + starts API on port 8088
```

### 8. Run extractors individually (optional)

```bash
python extractors/youtube.py                # Extract all pending YouTube links via TokScript MCP
python extractors/youtube.py URL            # Extract a single URL via TokScript MCP
python extractors/youtube.py --dry-run      # Preview pending YouTube links

python extractors/tokscript_parser.py       # Parse all CSVs in csv_inbox/ (fallback)

python extractors/spotify_to_youtube.py          # Convert all pending Spotify podcasts
python extractors/spotify_to_youtube.py URL      # Convert a single Spotify URL
python extractors/spotify_to_youtube.py --dry-run # Preview pending Spotify links
```

Transcript extraction uses a shared runtime layer so the same repo can be operated by Claude or Codex without forking the core pipeline logic.

Relevant env vars:
- `AGENT_RUNTIME=claude|codex`
- `EXTRACTOR_BACKEND=claude_cli|agent_prompt`
- `EXTRACTOR_MODEL=sonnet`
- `EXTRACTOR_BATCH_SIZE=10`
- `EXTRACTOR_BUDGET_USD=0.5`

Recommended defaults:
- Claude session: `AGENT_RUNTIME=claude`, leave `EXTRACTOR_BACKEND` empty or set it to `claude_cli`
- Codex session: `AGENT_RUNTIME=codex`, set `EXTRACTOR_BACKEND=agent_prompt`

`agent_prompt` writes a runtime-specific extraction prompt and queued job into `csv_inbox/mcp_extracts/` and `csv_inbox/extraction_jobs/` for a Codex session to execute manually. This is the current Codex-compatible bridge until extraction is fully decoupled from subprocess-based agent execution.

Queued prompt jobs can be inspected with:

```bash
python extractors/extraction_jobs.py       # List pending extraction jobs
python extractors/extraction_jobs.py --next
python extractors/extraction_jobs.py --id JOB_ID
python extractors/extraction_jobs.py --claim JOB_ID --worker codex
python extractors/extraction_jobs.py --release JOB_ID
python extractors/extraction_jobs.py --stale
python extractors/extraction_jobs.py --prune-stale
python extractors/extraction_jobs.py --complete JOB_ID --output-file /path/to/agent_output.txt
python extractors/extraction_jobs.py --fail JOB_ID --error "reason"
```

Recommended Codex-native flow:
1. `AGENT_RUNTIME=codex EXTRACTOR_BACKEND=agent_prompt python orchestrator.py`
2. `python extractors/extraction_jobs.py --next`
3. `python extractors/extraction_jobs.py --claim JOB_ID --worker codex`
4. Run the job via Codex MCP tools
5. `python extractors/extraction_jobs.py --complete JOB_ID --output-file /path/to/agent_output.txt`

Stale-job cleanup:

- `python extractors/extraction_jobs.py --stale` reports queued jobs whose URLs are no longer present in the live pending Notion queue
- `python extractors/extraction_jobs.py --prune-stale` archives those jobs into `csv_inbox/extraction_jobs/stale/`

### 9. Run the classifier (optional, runs automatically in orchestrator)

```bash
python engines/classifier.py                # Classify all transcribed links (via OpenRouter)
python engines/classifier.py --limit=10     # Classify only the first N links
python engines/classifier.py --retry-errors # Retry links that failed classification
python engines/classifier.py --list         # List links pending classification
python engines/classifier.py --id PAGE_ID   # Classify a specific link
python engines/classifier.py --dry-run      # Preview what would be classified
```

For manual Codex or Claude sessions, you can also classify in-session instead of using OpenRouter:

1. fetch a `transcribed` link from Notion
2. classify it in-session using the same 9-tag schema
3. update the page to `classified`
4. append extracted knowledge into the matching Obsidian files

That path is useful when free OpenRouter models are slow or rate-limited, but it is not the unattended path.

### 10. Run ideation pipeline (via Claude Code or shared save flow)

```bash
python engines/ideation.py                  # Pipeline mode (default): 4-skill ideation
python engines/ideation.py --list           # List links tagged 'generate_ideas'
python engines/ideation.py --id PAGE_ID     # Process a specific link
python engines/ideation.py --legacy         # Legacy single-shot prompt mode
python engines/ideation.py --save '{"page_id":"...","url":"..."}' '[...]'  # Save approved ideas
```

`--save` now validates idea payloads, skips obvious duplicates for the same source, and only marks the source link `processed` if at least one new idea is actually created.

### 11. Run captions (via Claude Code or shared save flow)

```bash
python engines/captions.py --list           # List filmed ideas ready for captions
python engines/captions.py --id PAGE_ID     # Generate captions for a specific idea
python engines/captions.py --save PAGE_ID '{"caption_tiktok":"...","caption_instagram":"..."}'
python engines/captions.py --save PAGE_ID '{"caption_tiktok":"...","caption_youtube":{"title":"...","description":"..."},"mark_captioned":true}'
```

Caption saves support partial updates. Status stays unchanged unless you explicitly pass either `"mark_captioned": true` or `"status": "captioned"`.

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with supported types |
| `/status` | Show counts for all content types |
| `/list` | Show recent links from all types |
| `/list <type>` | Show recent links for one type (e.g. `/list podcasts`) |
| `/note <text>` | Add a note to the last saved link (syncs to Notion) |
| `/clear` | Clear all pending links |
| `/clear <type>` | Clear one type (e.g. `/clear tiktoks`) |

---

## Content Categories

| Type | Detected From | Notion Category | Notion on save? | Transcribed by |
|------|---------------|-----------------|-----------------|----------------|
| TikToks | `tiktok.com`, `vm.tiktok.com` | tiktok | No (text file only) | TokScript MCP |
| Reels | `instagram.com/reel/` | reels | No (text file only) | TokScript MCP |
| YT Shorts | `youtube.com/shorts/` | yt_shorts | Yes | TokScript MCP |
| Long-form YT | `youtube.com/watch`, `youtu.be` | podcast / long_form | Yes | TokScript MCP |
| Carousels | `instagram.com/p/` | carousel | Yes | — |
| Podcasts | `spotify.com` | podcast | Yes | Spotify converter → TokScript MCP |
| X Posts | `twitter.com`, `x.com` | x_post | Yes | — |
| LinkedIn | `linkedin.com/posts`, `linkedin.com/feed/update` | linkedin | Yes | — |
| Reddit | `reddit.com` | reddit | Yes | — |

### What The Orchestrator Does Not Process Yet

These categories are intentionally stored but not auto-transcribed by the current orchestrator:

- `carousel`
- `linkedin`
- `reddit`
- `x_post`

Those links remain `pending` until you either build a dedicated processor for them or manually triage them into another status. This is expected behavior, not a stuck queue bug.

---

## Notion Databases

### Links Queue

Inbox of raw content links. Each link has a URL, category, notes, status, and (after extraction) transcript, original caption/description, and metadata. After classification, each link gets non-exclusive content tags and an AI summary.

**Content Tags (multi-select):** `content_idea`, `content_lesson`, `hook_pattern`, `tool_discovery`, `workflow`, `ai_knowledge`, `business_knowledge`, `knowledge_nugget`, `news`, `inspiration`

**Statuses:** `pending` > `transcribed` > `classified` > `generate_ideas` > `processed` > `archived` | `postponed` | `learning` | `inspiration` | `other` | `converted` (Spotify > YouTube)

### Content Ideas

Generated ideas linked back to source material. Each idea has a short title, description, angle, 5 hooks, format, urgency, score, filming setup, filming priority, and (after filming) platform-specific captions.

**Key fields:**
- **Name** — Short punchy title (e.g. "You Don't Need AI Agents. You Need a Checklist First.")
- **Hook 1-5** — 5 viral hooks per idea using proven patterns (authority, contrarian, data, story, cautionary)
- **Score** — Creative director score (1-10) for idea quality
- **Top Pick** — Checkbox for the #1 idea from each batch
- **Filming Setup** — `talking_head`, `screen_recording`, `walk_and_talk`, `studio`, `split_screen_react`
- **Filming Priority** — `film_now` (red), `film_soon` (orange), `batch_next` (blue), `shelved` (gray)

**Statuses:** `new` > `queued` > `filming_today` > `filmed` > `captioned` > `posted` > `archived`

**Caption save notes:**
- `Caption TikTok`, `Caption Instagram`, and `Caption LinkedIn` are saved as plain rich text.
- `Caption YouTube` is stored as a single rich text field, but the save command accepts either a plain string or an object with `title` and `description`.
- Saving one platform does not automatically advance the status.

---

## File Structure

```
content-pipeline-bot/
├── .env                              # Secrets (Telegram + Notion tokens + DB IDs + Obsidian path)
├── .env.example                      # Template for .env
├── requirements.txt                  # Python dependencies
├── README.md                         # This file
├── CLAUDE.md                         # Content Agent project brain (read by Claude Code on startup)
├── CONTENT_ENGINE_PLAN.md            # Build plan + backlog + session continuity doc
│
├── bot/                              # Telegram bot (always running)
│   ├── config.py                     # Loads env vars, defines content types
│   └── main.py                       # Bot handlers, Notion sync, /note support
│
├── extractors/                       # Transcript extraction tools
│   ├── youtube.py                    # YouTube transcripts via shared runtime backend
│   ├── runtime.py                    # Claude/Codex extraction runtime selection + job creation
│   ├── extraction_jobs.py            # Codex-native extraction job queue, completion, stale cleanup
│   ├── tokscript_parser.py           # TokScript CSV parser — fallback for TikTok/IG transcripts
│   ├── mcp_normalizer.py             # Normalizes TokScript MCP responses + platform detection
│   └── spotify_to_youtube.py         # Spotify podcast > YouTube URL converter
│
├── engines/                          # Pipeline engines
│   ├── classifier.py                 # Classifier v2: OpenRouter API (Qwen), non-exclusive tags, knowledge extraction, Obsidian writes
│   ├── ideation.py                   # 4-skill ideation pipeline (or --legacy for single-shot)
│   └── captions.py                   # Filmed idea > platform captions
│
├── prompts/                          # Prompt templates + brand guidelines
│   ├── classify_prompt.md            # Classifier prompt — 9 tag types, non-exclusive extraction
│   ├── creator_context.md            # Compact brand context (positioning, ICP, voice, pillars)
│   ├── ideation_pipeline.md          # 4-skill pipeline instructions
│   ├── brand_identity.md             # Full brand identity: mission, values, service areas
│   ├── brand_voice.md                # Voice & language rules, niche language banks
│   ├── brand_content_strategy.md     # Content strategy: funnel, pillars, frames, CTAs
│   ├── captions.txt                  # Caption prompt template
│   ├── ideation.txt                  # Legacy single-shot ideation prompt
│   └── ideation_legacy.txt           # Backup of original ideation prompt
│
├── skills/                           # Claude Code /ca-* skill definitions
│   ├── ca-help.md                    # Show all commands and usage tips
│   ├── ca-brief.md                   # Morning content brief skill
│   ├── ca-extract.md                 # Extract transcripts via TokScript MCP (all platforms)
│   ├── ca-classify.md                # Interactive classifier skill
│   ├── ca-ideate.md                  # Ideation from queued links or a topic
│   ├── ca-research.md                # Research a topic, save to knowledge files
│   ├── ca-captions.md                # Captions after filming
│   └── ca-sparring.md                # Creative discussion and pushback mode
│
├── api/                              # FastAPI backend (port 8088)
│   ├── server.py                     # API routes for dashboard
│   ├── notion.py                     # Notion database operations
│   └── test_server.py               # API tests
│
├── frontend/                         # React + Vite dashboard
│   ├── src/                          # Components: App, Layout, IdeaCard, IdeaDetail, FilterBar
│   ├── dist/                         # Built output
│   └── vite.config.js               # Vite config (proxies /api to port 8088)
│
├── knowledge/                        # Local fallback for Obsidian knowledge files
│
├── tests/                            # Test suite
│   ├── test_classifier.py            # Classifier tests: parsing, formatting, fallback, dedup
│   ├── test_runtime.py               # Runtime tests: Claude/Codex routing, extraction jobs, stale cleanup
│   ├── test_ideation.py              # Idea save validation and duplicate handling
│   ├── test_captions.py              # Caption save validation and status handling
│   └── test_mcp_normalizer.py        # EXTRACT_RESULT parsing and backup behavior
│
├── orchestrator.py                   # Evening pipeline (MCP extraction + CSV fallback + classification)
├── run.sh                            # Single-command startup (builds frontend + starts API)
├── csv_inbox/                        # Drop TokScript CSVs here (fallback if MCP unavailable)
│   ├── processed/                    # Processed CSVs moved here automatically
│   ├── mcp_extracts/                 # Backup JSONs + raw outputs from MCP extraction runs
│   └── extraction_jobs/              # Queued Codex extraction jobs (plus stale archive)
├── links/                            # Text file backups (legacy, still written to)
├── migrate_links.py                  # One-time migration script (already run)
├── upload_to_notion.py               # TokScript CSV bulk uploader — uploads CSV exports to Notion Links Queue
└── validate_env.py                   # Environment + connectivity validation
```

---

## Tech Stack

- **Python 3.9+** with `python-telegram-bot>=20.0`
- **React + Vite** dashboard for idea review
- **FastAPI** backend serving the dashboard API (port 8088)
- **Notion API** (REST) for database reads/writes from bot + scripts
- **Notion MCP** for interactive bulk operations from Claude or Codex sessions
- **Obsidian** for knowledge file storage (synced via iCloud)
- **TokScript MCP** for transcript extraction across all platforms (YouTube, TikTok, Instagram)
- **OpenRouter API** for unattended classification (cheap/free model option, 30s retry backoff on rate limits)
- **Claude CLI** (`claude -p --model sonnet`) for fully automated MCP extraction subprocesses
- **Codex MCP session** for manual/session-native extraction and classification
- **yt-dlp** for YouTube search (Spotify converter)
- **Spotify oEmbed API** for podcast episode metadata (no auth needed)
- **Claude Code** for interactive ideation (4-skill pipeline), caption generation, and Content Agent skills
- **ChatGPT Codex** for local repo operation, MCP execution, and in-session classification

---

## Operational Caveats

- `Claude Automated` is the most unattended mode today, but extraction spend comes from Anthropic credits because Claude CLI owns the MCP subprocess path.
- `Hybrid` reduces Anthropic usage because classification moves to OpenRouter, but cheap or free models can be slow and occasionally rate-limit or timeout.
- `Codex Session-Native` avoids Claude usage for the operator session, but extraction is currently session-driven through queued jobs rather than fully unattended subprocess automation.
- The orchestrator intentionally leaves unsupported categories in `pending`. If you see a large pending queue made of `linkedin`, `carousel`, `reddit`, or `x_post`, that is expected.
- Old queued extraction jobs can become stale after the live Notion queue changes. Use `python extractors/extraction_jobs.py --stale` and `--prune-stale`.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.4.0 | 2026-04-06 | Dual-agent runtime hardening: shared Claude/Codex extraction runtime, Codex extraction job queue with claim/release/complete/fail flow, stale-job cleanup, environment validation, ideation/caption save validation, Spotify orchestration wiring, classifier fallback handling, and updated docs for Claude automated, hybrid, and Codex session-native operation. |
| 2.3.0 | 2026-04-05 | OpenRouter integration: classifier now uses OpenRouter API with free Qwen model (`qwen/qwen3.6-plus:free`) instead of Claude CLI subprocess — zero Claude token cost for classification. 30s retry backoff on 429 rate limits. New `--limit=N` flag for batch-size control. `--retry-errors` flag for re-running failed links. Configurable delay between API calls (`CLASSIFIER_DELAY`). `upload_to_notion.py` CSV uploader for TokScript bulk exports. |
| 2.2.0 | 2026-04-05 | TokScript MCP integration: all transcript extraction (YouTube, TikTok, Instagram) now runs via TokScript MCP tools through Claude CLI subprocess — no more manual CSV exports or youtube-transcript-api IP blocks. Full transcripts saved to Notion (multi-block rich_text, up to 100K chars). New `/ca-extract` skill for interactive MCP extraction. `mcp_normalizer.py` for response normalization. Legacy youtube-transcript-api + yt-dlp code preserved as commented reference. |
| 2.1.0 | 2026-03-31 | Classifier v2: 4 new knowledge tag types (ai_knowledge, business_knowledge, knowledge_nugget, news), non-exclusive tagging with per-file framing, Obsidian #tags on every entry, heading-based deduplication, news date stamps. 9 Obsidian knowledge files. Notion Content Tags updated. 27 tests. |
| 2.0.0 | 2026-03-29 | Content Agent upgrade: classifier engine, auto-classification in orchestrator, 7 /ca-* skills, knowledge files system (Obsidian vault + local fallback), classify_prompt.md. React + FastAPI dashboard with FilterBar, IdeaCard, IdeaDetail. `run.sh` for single-command startup. |
| 1.3.0 | 2026-03-18 | 4-skill ideation pipeline: content-idea-generator → viral-hook-creator → creative-director → de-ai-ify. Score, Top Pick, Filming Setup, Filming Priority fields. Morning Menu view sorted by score. |
| 1.2.0 | 2026-03-18 | "Generate Ideas" status workflow. Triage statuses: learning, inspiration, postponed, other. Original Caption in ideation. 5 Content Ideas views. |
| 1.1.0 | 2026-03-18 | TikToks/Reels no longer pushed to Notion on save. YouTube descriptions captured. TokScript retry logic. Duplicate URL cleanup. |
| 1.0.0 | 2026-03-18 | Phase 1 MVP: Telegram bot, Notion sync, YouTube extractor, TokScript parser, Spotify converter, ideation engine, caption generator, orchestrator. |
| 0.1.0 | 2026-03-09 | Original video-pipeline bot: Telegram link collector with text file storage. |
