# Autom8Lab Content Engine

**Version:** 2.0.0
**Last updated:** 2026-03-29
**Phase:** 2 — Content Agent (Conversational Sparring Partner)

Turn raw video links (sent via Telegram) into actionable content ideas overnight, with caption generation after filming. Now upgraded with a Content Agent layer — a conversational sparring partner that knows your brand, your backlog, and your principles.

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
  ├── YouTube Extractor ── auto-transcribes podcasts, YT shorts, long-form + descriptions
  ├── Spotify Converter ── finds YouTube version of Spotify podcasts
  ├── TokScript Parser ─── parses CSV exports for TikTok/IG transcripts + captions
  └── Classifier ────────── auto-tags links with topic, format, and angle signals
  |
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
Content Ideas DB (Notion)
  |
  v  You film it, then...
  |
Caption Generator (interactive via Claude Code)
  |  Platform-specific captions for TikTok, IG, YouTube, LinkedIn
  v
You post it
```

---

## Content Agent

The Content Agent is an upgrade from a capture-and-process tool into a conversational content sparring partner. Instead of just running scripts, you can now open a Claude Code session and talk through ideas, get a morning brief, run classification interactively, or spar on hooks and angles — all with context from your Notion backlog, your brand principles, and your knowledge files. The agent gets smarter over time as your knowledge files grow: every principle, proven hook, and tool reference you add makes future briefs, ideation, and sparring sessions more grounded in your actual thinking.

### `/ca-*` Commands

| Command | What it does |
|---------|-------------|
| `/ca-help` | Show all Content Agent commands and usage tips |
| `/ca-brief` | Morning content brief — pipeline status, top ideas, one principle, one tool |
| `/ca-classify` | Run the classifier on transcribed links — auto-tag with topic, format, and angle signals |
| `/ca-ideate` | Generate content ideas from queued links or a freeform topic, informed by knowledge files |
| `/ca-research` | Research a topic for content angles — search web, save findings to knowledge files |
| `/ca-captions` | Generate platform-ready captions after filming, using your voice and brand principles |
| `/ca-sparring` | Creative discussion mode — push back on weak ideas, reference your knowledge and principles |

### Daily Workflow (with Content Agent)

| When | What | How |
|------|------|-----|
| Morning | Get a content brief | `/ca-brief` in Claude Code — pipeline status, top 3 ideas to film, one principle, one tool |
| During the day | Save links | Send to Telegram bot |
| During the day | Freeform ideation or hook refinement | `/ca-sparring` or `/ca-research` in Claude Code — no scripts needed |
| Evening | Export TikToks/Reels | TokScript: paste links → export CSV → drop in `csv_inbox/` |
| Evening | Run pipeline | `python orchestrator.py` — now includes auto-classification after extraction |
| Evening | Triage links | In Notion, set each classified link to `generate_ideas`, `learning`, `inspiration`, `postponed`, or `other` |
| Evening | Generate ideas | `python engines/ideation.py` in Claude Code (or `/ca-ideate`) |
| After filming | Generate captions | `/ca-captions` in Claude Code |
| After filming | Post content | Copy captions from Notion, post manually |

### Knowledge Files

Knowledge files are the Content Agent's long-term memory. They capture your content principles, proven hooks, tools you reference, and raw ideas — and they're read automatically by `/ca-brief`, `/ca-ideate`, and `/ca-sparring` to ground responses in your actual thinking rather than generic best practices.

**Where they live:** `$OBSIDIAN_VAULT_PATH/content/` (Obsidian vault, synced across devices) with a local fallback at `knowledge/` in this repo. The agent tries the Obsidian path first and falls back silently if the file doesn't exist yet.

| File | What it contains |
|------|-----------------|
| `content-principles.md` | Your core beliefs about content — what you stand for, what you avoid, your POV |
| `hook-bank.md` | Proven hook structures and examples from your best-performing content |
| `tool-library.md` | Tools, frameworks, and systems you reference in your content |
| `idea-backlog.md` | Raw ideas, half-formed thoughts, and topics you want to explore |

---

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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
```

### 3. Run the Telegram bot

```bash
python bot/main.py
```

### 4. Run the evening pipeline

```bash
python orchestrator.py           # Full pipeline: CSV inbox + YouTube extraction + classification
python orchestrator.py --dry-run # Preview what would be processed
python orchestrator.py --status  # Show current queue counts
```

### 5. Run extractors individually (optional)

```bash
python extractors/youtube.py                # Transcribe all pending YouTube links
python extractors/youtube.py URL            # Transcribe a single URL
python extractors/youtube.py --dry-run      # Preview pending YouTube links

python extractors/tokscript_parser.py       # Parse all CSVs in csv_inbox/

python extractors/spotify_to_youtube.py          # Convert all pending Spotify podcasts
python extractors/spotify_to_youtube.py URL      # Convert a single Spotify URL
python extractors/spotify_to_youtube.py --dry-run # Preview pending Spotify links
```

### 6. Run the classifier (optional, runs automatically in orchestrator)

```bash
python engines/classifier.py                # Classify all transcribed links
python engines/classifier.py --list         # List links pending classification
python engines/classifier.py --id PAGE_ID   # Classify a specific link
python engines/classifier.py --dry-run      # Preview what would be classified
```

### 7. Run ideation pipeline (via Claude Code)

```bash
python engines/ideation.py                  # Pipeline mode (default): 4-skill ideation
python engines/ideation.py --list           # List links tagged 'generate_ideas'
python engines/ideation.py --id PAGE_ID     # Process a specific link
python engines/ideation.py --legacy         # Legacy single-shot prompt mode
```

### 8. Run captions (via Claude Code)

```bash
python engines/captions.py --list           # List filmed ideas ready for captions
python engines/captions.py --id PAGE_ID     # Generate captions for a specific idea
```

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
| TikToks | `tiktok.com`, `vm.tiktok.com` | tiktok | No (text file only) | TokScript CSV |
| Reels | `instagram.com/reel/` | reels | No (text file only) | TokScript CSV |
| YT Shorts | `youtube.com/shorts/` | yt_shorts | Yes | YouTube extractor |
| Carousels | `instagram.com/p/` | carousel | Yes | — |
| Podcasts | `youtube.com/watch`, `youtu.be`, `spotify.com` | podcast | Yes | YouTube extractor (Spotify converted first) |
| X Posts | `twitter.com`, `x.com` | x_post | Yes | — |
| LinkedIn | `linkedin.com/posts`, `linkedin.com/feed/update` | linkedin | Yes | — |
| Reddit | `reddit.com` | reddit | Yes | — |

---

## Notion Databases

### Links Queue

Inbox of raw content links. Each link has a URL, category, notes, status, and (after extraction) transcript, original caption/description, and metadata. After classification, each link also has auto-tagged topic, format, and angle signals.

**Statuses:** `pending` > `transcribed` > `classified` > `generate_ideas` > `processed` > `archived` | `postponed` | `learning` | `inspiration` | `other` | `converted` (Spotify > YouTube)

**Views:** All Links, Short Form, Podcasts, Carousels, LinkedIn, X Posts, Reddit

### Content Ideas

Generated ideas linked back to source material. Each idea has a short title (Name), a description, an angle, 5 hooks, format, urgency, score, filming setup, filming priority, and (after filming) platform-specific captions.

**Key fields:**
- **Name** — Short punchy title for the idea (e.g. "You Don't Need AI Agents. You Need a Checklist First.")
- **Description** — 2-3 sentence explanation of the idea angle
- **Hook 1-5** — 5 viral hooks per idea using proven patterns (authority, contrarian, data, story, cautionary)
- **Score** — Creative director score (1-10) for idea quality
- **Top Pick** — Checkbox for the #1 idea from each batch
- **Filming Setup** — Multi-select: `talking_head`, `screen_recording`, `walk_and_talk`, `studio`, `split_screen_react`
- **Filming Priority** — `film_now` (red), `film_soon` (orange), `batch_next` (blue), `shelved` (gray)

**Statuses:** `new` > `queued` > `filming_today` > `filmed` > `captioned` > `posted` > `archived`

**Views:** Morning Menu (sorted by score), Filming Today, Ready to Post, Posted (Last 7 Days), Archive

---

## File Structure

```
content-pipeline-bot/
├── .env                              # Secrets (Telegram + Notion tokens + DB IDs)
├── .env.example                      # Template for .env
├── requirements.txt                  # Python dependencies
├── README.md                         # This file
├── CONTENT_ENGINE_PLAN.md            # Build plan + backlog + session continuity doc
│
├── bot/                              # Telegram bot (always running)
│   ├── config.py                     # Loads env vars, defines content types
│   └── main.py                       # Bot handlers, Notion sync, /note support
│
├── extractors/                       # Transcript extraction tools
│   ├── youtube.py                    # YouTube transcripts + descriptions via youtube-transcript-api + yt-dlp
│   ├── tokscript_parser.py           # TokScript CSV parser for TikTok/IG transcripts + captions (with retry logic)
│   └── spotify_to_youtube.py         # Spotify podcast > YouTube URL converter
│
├── engines/                          # Pipeline scripts + Content Agent core
│   ├── ideation.py                   # 4-skill ideation pipeline (or --legacy for single-shot)
│   ├── captions.py                   # Filmed idea > platform captions
│   └── classifier.py                 # Auto-classification engine — topic, format, angle signals
│
├── skills/                           # Claude Code /ca-* skill definitions
│   ├── ca-help.md                    # Show all commands and usage tips
│   ├── ca-brief.md                   # Morning content brief skill
│   ├── ca-classify.md                # Interactive classifier skill
│   ├── ca-ideate.md                  # Ideation from queued links or a topic
│   ├── ca-research.md                # Research a topic, save to knowledge files
│   ├── ca-captions.md                # Captions after filming
│   └── ca-sparring.md                # Creative discussion and pushback mode
│
├── knowledge/                        # Local fallback for knowledge files (Obsidian preferred)
│   ├── content-principles.md         # Core content beliefs and POV
│   ├── hook-bank.md                  # Proven hook structures and examples
│   ├── tool-library.md               # Tools and frameworks referenced in content
│   └── idea-backlog.md               # Raw ideas and half-formed thoughts
│
├── prompts/                          # Prompt templates + brand guidelines
│   ├── ideation_pipeline.md          # 4-skill pipeline instructions (default)
│   ├── classify_prompt.md            # Classifier prompt — topic, format, angle extraction
│   ├── creator_context.md            # Compact brand context for ideation (positioning, ICP, voice, pillars)
│   ├── brand_identity.md             # Full brand identity: mission, values, service areas
│   ├── brand_voice.md                # Voice & language rules, translations, niche language banks
│   ├── brand_content_strategy.md     # Content strategy: funnel, pillars, frames, founder voice, CTAs
│   ├── ideation.txt                  # Legacy single-shot ideation prompt
│   ├── ideation_legacy.txt           # Backup of original ideation prompt
│   └── captions.txt                  # Caption prompt template
│
├── orchestrator.py                   # Evening pipeline (CSV + YouTube + classification + summary)
├── csv_inbox/                        # Drop TokScript CSVs here
│   └── processed/                    # Processed CSVs moved here automatically
├── links/                            # Text file backups (legacy, still written to)
│   ├── pending_tiktoks.txt
│   ├── pending_reels.txt
│   ├── pending_yt_shorts.txt
│   ├── pending_carousels.txt
│   ├── pending_podcasts.txt
│   ├── pending_x.txt
│   ├── pending_linkedin.txt
│   └── pending_reddit.txt
│
├── migrate_links.py                  # One-time migration script (already run)
└── upload_to_notion.py               # Legacy TokScript uploader (deprecated)
```

---

## Tech Stack

- **Python 3.9+** with `python-telegram-bot>=20.0`
- **Notion API** (REST) for database reads/writes from bot + scripts
- **Notion MCP** for database creation, views, bulk operations via Claude Code
- **youtube-transcript-api** for YouTube transcript extraction
- **yt-dlp** for video metadata + YouTube search (Spotify converter)
- **Spotify oEmbed API** for podcast episode metadata (no auth needed)
- **Claude Code** for interactive ideation (4-skill pipeline), caption generation, and Content Agent skills
- **Claude Code Skills** — content-idea-generator, viral-hook-creator, creative-director, de-ai-ify, ca-brief, ca-classify, ca-ideate, ca-research, ca-captions, ca-sparring

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-03-29 | Content Agent upgrade: classifier engine (engines/classifier.py), auto-classification in orchestrator, 7 /ca-* skills (ca-help, ca-brief, ca-classify, ca-ideate, ca-research, ca-captions, ca-sparring), knowledge files system (Obsidian vault + local fallback), classify_prompt.md. New `classified` status in Links Queue. |
| 1.3.0 | 2026-03-18 | 4-skill ideation pipeline replaces single-shot prompt: content-idea-generator (quick mode, 5 ideas) → viral-hook-creator (5 hooks per idea) → creative-director (score, rank, kill weak ideas) → de-ai-ify (clean up language). New Notion fields: Score, Top Pick, Filming Setup (multi-select), Filming Priority. Hook 1-5 replace single Suggested Hook. Morning Menu view now sorted by score with filming columns. Creator context file for positioning/ICP. Legacy mode available via --legacy flag. |
| 1.2.0 | 2026-03-18 | "Generate Ideas" status workflow: ideation.py now only processes links you've tagged `generate_ideas` in Notion (not all transcribed). New triage statuses: `learning`, `inspiration`, `postponed`, `other` for non-content links. Original Caption now included in ideation prompt for better context. Original URL field added to Content Ideas DB. 5 Content Ideas views: Morning Menu, Filming Today, Ready to Post, Posted, Archive. Python 3.9 compatibility fix. |
| 1.1.0 | 2026-03-18 | TikToks/Reels no longer pushed to Notion on save (avoids duplicates — Notion rows created via TokScript CSV only). YouTube extractor now captures video descriptions into Original Caption field. TokScript parser has retry logic for Notion API timeouts. Cleaned up 41 duplicate shortened TikTok URLs. |
| 1.0.0 | 2026-03-18 | Phase 1 MVP complete: Telegram bot with Notion sync, YouTube extractor, TokScript parser, Spotify converter, ideation engine, caption generator, orchestrator. 6 filtered views on Links Queue. /note syncs to Notion. Original Caption field for full captions/descriptions. |
| 0.1.0 | 2026-03-09 | Original video-pipeline bot: Telegram link collector with text file storage |
