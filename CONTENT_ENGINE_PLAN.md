# Content Engine — Plan & Status

**Project:** Autom8Lab Content Engine
**Owner:** Cosmo
**Created:** 2026-03-16
**Last updated:** 2026-03-29
**Status:** Phase 2 Complete — Content Agent active

> Start each Claude Code session with: "Read CONTENT_ENGINE_PLAN.md and pick up where we left off."

---

## Current State — What's Built

All Phase 1 and Phase 2 components are **complete**. The system is fully functional for daily use with the Content Agent layer active.

### Core Components

| Component | File | Status | What it does |
|-----------|------|--------|-------------|
| Telegram Bot | `bot/main.py` | ✅ Running | Receives links, categorizes via regex, saves to text file + Notion (except TikToks/Reels) |
| YouTube Extractor | `extractors/youtube.py` | ✅ Done | Transcribes YT Shorts, podcasts, long-form via `youtube-transcript-api` + `yt-dlp`. Extracts descriptions into Original Caption |
| TokScript Parser | `extractors/tokscript_parser.py` | ✅ Done | Parses CSV exports for TikTok/IG transcripts + captions. Creates Notion rows. Retry logic for API timeouts |
| Spotify Converter | `extractors/spotify_to_youtube.py` | ✅ Done | Finds YouTube version of Spotify podcasts via oEmbed + yt-dlp search. Creates YouTube row, marks Spotify row as converted |
| Classifier | `engines/classifier.py` | ✅ Done | Auto-classifies transcribed links with topic, format, and angle signals via Claude Code. Writes classification to Notion. Runs automatically in orchestrator |
| Ideation Pipeline | `engines/ideation.py` | ✅ Done | 4-skill pipeline via Claude Code: content-idea-generator → viral-hook-creator → creative-director → de-ai-ify. 5 ideas per video, 5 hooks per idea, scored and ranked |
| Caption Generator | `engines/captions.py` | ✅ Done | Interactive via Claude Code. Generates TikTok/IG/YouTube/LinkedIn captions for filmed ideas |
| Orchestrator | `orchestrator.py` | ✅ Done | Evening pipeline: CSV inbox → Spotify converter → YouTube extractor → classifier → summary. Supports `--dry-run` and `--status` |

### Content Agent Skills

| Skill | File | Status | What it does |
|-------|------|--------|-------------|
| ca-help | `skills/ca-help.md` | ✅ Done | Show all /ca-* commands and usage tips |
| ca-brief | `skills/ca-brief.md` | ✅ Done | Morning brief: pipeline status, top 3 ideas, one principle, one tool |
| ca-classify | `skills/ca-classify.md` | ✅ Done | Interactive classification of transcribed links |
| ca-ideate | `skills/ca-ideate.md` | ✅ Done | Generate ideas from queued links or a freeform topic, informed by knowledge files |
| ca-research | `skills/ca-research.md` | ✅ Done | Research a topic for content angles, save findings to knowledge files |
| ca-captions | `skills/ca-captions.md` | ✅ Done | Generate platform captions after filming using voice and brand principles |
| ca-sparring | `skills/ca-sparring.md` | ✅ Done | Creative discussion mode — push back on weak ideas, reference knowledge and principles |

### Knowledge Files System

Knowledge files give the Content Agent long-term memory. They live in `$OBSIDIAN_VAULT_PATH/content/` (synced across devices) with a local fallback at `knowledge/` in the repo.

| File | Used by |
|------|--------|
| `content-principles.md` | ca-brief, ca-sparring, ca-ideate |
| `hook-bank.md` | ca-brief, ca-ideate, ca-sparring |
| `tool-library.md` | ca-brief, ca-sparring |
| `idea-backlog.md` | ca-brief, ca-ideate |

### Notion Databases

| Database | ID | Status |
|----------|-----|--------|
| Links Queue | `325a44c6f32f8086a1e4e1b10d6e6de9` | ✅ Active |
| Content Ideas | `325a44c6f32f80fb9ff3f0760c28fb48` | ✅ Active |

**Links Queue fields:** Name, Link URL, Category, Timestamp, Notes, Transcript, Original Caption, Source Views, Source Likes, Duration, Author, Status, Topic, Format, Angle (added in Phase 2)

**Links Queue statuses:** `pending` > `transcribed` > `classified` > `generate_ideas` > `processed` > `archived` | `postponed` | `learning` | `inspiration` | `other` | `converted`

**Links Queue views:** All Links, 🎬 Short Form, 🎙️ Podcasts, 🎠 Carousels, 💼 LinkedIn, 𝕏 X Posts, 🤖 Reddit

**Content Ideas fields:** Name (title), Description, Source Link (relation), Angle, Hook 1-5, Format, Urgency, Reasoning, Score, Top Pick, Filming Setup (multi_select), Filming Priority, Status, Frame Type (multi_select), Topic Cluster, Original URL, filmed_date, posted_date, caption_tiktok, caption_instagram, caption_youtube, caption_linkedin, post URLs

**Content Ideas views:** ☀️ Morning Menu (sorted by Score desc), 🎬 Filming Today, ✍️ Ready to Post, ✅ Posted (Last 7 Days), 📦 Archive

### Key Design Decisions

1. **TikToks & Reels are NOT pushed to Notion on save** — text file only. Notion rows are created when TokScript CSV is processed. This avoids duplicates caused by shortened vs full URLs.
2. **YT Shorts ARE pushed to Notion immediately** — they get transcribed directly by the YouTube extractor.
3. **Spotify podcasts use a hybrid approach** — oEmbed API (no auth) for episode metadata, yt-dlp search for YouTube match. No Spotify Developer credentials needed.
4. **Original Caption field** stores full video descriptions (YouTube) or full captions (TikTok/Reels). Name field is truncated to ~60 chars.
5. **Text files are kept as backup** for all content types, even when Notion is the primary store.
6. **Ideation and captions run interactively** via Claude Code, not as automated API calls.
7. **Classification runs automatically** in the evening orchestrator pipeline after transcript extraction, with `classify` status added to the Links Queue flow.
8. **Knowledge files use Obsidian vault as primary** — the agent tries `$OBSIDIAN_VAULT_PATH/content/` first and falls back to `knowledge/` silently. This keeps knowledge synced across devices without manual copying.

---

## Daily Workflow

| # | When | Who | What | How |
|---|------|-----|------|-----|
| 1 | Morning | Cosmo | Get a content brief | `/ca-brief` in Claude Code |
| 2 | During the day | Cosmo | Save links | Send to Telegram bot |
| 3 | During the day | Cosmo + Claude | Freeform ideation or research | `/ca-sparring` or `/ca-research` in Claude Code |
| 4 | Evening | Cosmo | Export TikToks/Reels | TokScript: paste links from text file → export CSV → drop in `csv_inbox/` |
| 5 | Evening | System | Run pipeline | `python orchestrator.py` (CSV parser + Spotify converter + YouTube extractor + classifier) |
| 6 | Evening | Cosmo | Triage links | In Notion, set each classified link to `generate_ideas`, `learning`, `inspiration`, `postponed`, or `other` |
| 7 | Evening | Cosmo + Claude | Generate ideas | `python engines/ideation.py` in Claude Code — 4-skill pipeline |
| 8 | Morning | Cosmo | Pick what to film | Check "Morning Menu" view — sorted by score, top picks flagged, filming setup shown |
| 9 | — | Cosmo | Film it | — |
| 10 | After filming | Cosmo + Claude | Generate captions | `/ca-captions` in Claude Code |
| 11 | After filming | Cosmo | Post content | Copy captions from Notion, post manually |

---

## Backlog — What's Left To Do

> Pick these off when you have time. Start a Claude Code session with: "Read the plan and check the backlog."

### Ready to Build

| # | Task | Context | Priority |
|---|------|---------|----------|
| B7 | **Automate orchestrator via cron** | Currently runs manually. Could run at 10 PM daily via crontab. | Medium |
| B8 | **X/LinkedIn/Reddit transcript extraction** | These content types currently have no transcript extraction. Could use web scraping or platform APIs. | Low — text-based content, less need for transcripts |
| B13 | **Weekly digest skill (`/ca-digest`)** | Summarize the week's content performance, what was filmed vs posted, and top ideas still in backlog. Pull from Notion, output a scannable report. | Medium |
| B14 | **Trend detection in classifier** | Identify when multiple links in a short window share the same topic signal — surface as a "trending topic" flag in the brief. | Medium |
| B15 | **Obsidian skills integration** | `/ca-note` to save a quick thought to `idea-backlog.md` directly, `/ca-principles` to update `content-principles.md` from a conversation. Keep knowledge files fresh without manual editing. | Medium |
| B16 | **Scheduled classification (cron)** | Run classifier automatically overnight, separate from the evening orchestrator, so morning briefs always reflect the freshest classifications. | Low |

### Deferred / Nice-to-Have

| # | Task | Context | Priority |
|---|------|---------|----------|
| B9 | **Spotify Developer app** | Would give access to full Spotify API (richer metadata). Currently using free oEmbed endpoint which works fine. | Low — oEmbed works |
| B10 | **Verify Spotify→YouTube match accuracy** | Some YouTube search results may not be the exact episode. Could add manual confirmation step. | Low — spot-check occasionally |
| B11 | **Carousel content extraction** | Instagram carousels have no transcript, but could extract caption text via scraping. | Low — Week 2+ |

### Completed (Cleared from Active Backlog)

| # | Task | Completed |
|---|------|-----------|
| — | Content Agent upgrade | ✅ Phase 2 complete: classifier, 7 /ca-* skills, knowledge files system |
| — | Classifier engine | ✅ `engines/classifier.py` — auto-tags topic, format, angle. Integrated into orchestrator |
| — | classify_prompt.md | ✅ Prompt for Claude-based classification |
| — | 7 /ca-* skills | ✅ ca-help, ca-brief, ca-classify, ca-ideate, ca-research, ca-captions, ca-sparring |
| — | Knowledge files system | ✅ Obsidian vault primary, local `knowledge/` fallback |
| B5 | Content Ideas views | ✅ Morning Menu, Filming Today, Ready to Post, Posted, Archive |
| B12 | "Generate Ideas" status workflow | ✅ Added `generate_ideas` status. `ideation.py` queries `status = generate_ideas`. After ideas saved, source marked `processed`. |
| B1 | Spotify → YouTube converter | ✅ Built `extractors/spotify_to_youtube.py` — 10/13 converted on first run |
| B2 | Split short_form into tiktok/reels/yt_shorts | ✅ Bot regex + Notion categories updated, 35 existing rows migrated |
| B3 | Links Queue views (per category) | ✅ 6 filtered views created via Notion MCP |
| B4 | Share Notion DBs with bot integration | ✅ Bot 📋 emoji working |
| B6 | Frame Clusters on Content Ideas | ✅ Frame Type (multi_select) + Topic Cluster (rich_text) fields added |
| — | YouTube description extraction | ✅ `youtube.py` now captures video descriptions into Original Caption field |
| — | TokScript parser retry logic | ✅ 3 retries with exponential backoff for Notion API timeouts |
| — | TikTok/Reels deferred Notion push | ✅ Bot skips Notion for TikToks/Reels, rows created via TokScript CSV only |
| — | /note syncs to Notion | ✅ `append_note_to_notion()` reads existing notes, appends new note |
| — | Duplicate TikTok cleanup | ✅ 41 shortened-URL duplicate rows archived |
| — | Original Caption field | ✅ Full captions/descriptions stored separately from truncated Name |
| — | Original URL on Content Ideas | ✅ Direct link to source video from Content Ideas DB |
| — | 4-skill ideation pipeline | ✅ content-idea-generator → viral-hook-creator → creative-director → de-ai-ify |
| — | Hook 1-5 fields | ✅ 5 hooks per idea replacing single Suggested Hook |
| — | Score + Top Pick + Filming Setup/Priority | ✅ Creative director scoring, filming categorization |
| — | Python 3.9 compatibility | ✅ `from __future__ import annotations` in bot/main.py |

---

## Reference

### Content Categories

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

### File Structure

```
content-pipeline-bot/
├── .env                              # Secrets (Telegram + Notion tokens + DB IDs)
├── .env.example                      # Template for .env
├── requirements.txt                  # Python dependencies
├── README.md                         # User-facing docs
├── CONTENT_ENGINE_PLAN.md            # This file — plan, status, backlog
│
├── bot/                              # Telegram bot (always running)
│   ├── config.py                     # Loads env vars, defines content types
│   └── main.py                       # Bot handlers, Notion sync, /note support
│
├── extractors/                       # Transcript extraction tools
│   ├── youtube.py                    # YouTube transcripts + descriptions via youtube-transcript-api + yt-dlp
│   ├── tokscript_parser.py           # TokScript CSV parser for TikTok/IG (with retry logic)
│   └── spotify_to_youtube.py         # Spotify podcast → YouTube URL converter
│
├── engines/                          # Pipeline scripts + Content Agent core
│   ├── ideation.py                   # 4-skill ideation pipeline (or --legacy for single-shot)
│   ├── captions.py                   # Filmed idea → platform captions
│   └── classifier.py                 # Auto-classification engine
│
├── skills/                           # Claude Code /ca-* skill definitions
│   ├── ca-help.md
│   ├── ca-brief.md
│   ├── ca-classify.md
│   ├── ca-ideate.md
│   ├── ca-research.md
│   ├── ca-captions.md
│   └── ca-sparring.md
│
├── knowledge/                        # Local fallback for knowledge files
│   ├── content-principles.md
│   ├── hook-bank.md
│   ├── tool-library.md
│   └── idea-backlog.md
│
├── prompts/                          # Prompt templates for engines
│   ├── ideation_pipeline.md          # 4-skill pipeline instructions (default)
│   ├── classify_prompt.md            # Classifier prompt
│   ├── creator_context.md            # Compact brand context for ideation
│   ├── brand_identity.md             # Full brand identity
│   ├── brand_voice.md                # Voice & language rules
│   ├── brand_content_strategy.md     # Content strategy
│   ├── ideation.txt                  # Legacy single-shot ideation prompt
│   └── captions.txt                  # Caption prompt template
│
├── orchestrator.py                   # Evening pipeline (CSV + Spotify + YouTube + classifier + summary)
├── csv_inbox/                        # Drop TokScript CSVs here
│   └── processed/                    # Processed CSVs moved here automatically
├── links/                            # Text file backups (all content types)
├── migrate_links.py                  # One-time migration script (already run)
└── upload_to_notion.py               # Legacy TokScript uploader (deprecated)
```

### Ideation Pipeline (4-skill process)

| Step | Skill | What it does |
|------|-------|-------------|
| 1 | `content-idea-generator` (quick mode) | 5 ideas per video — quality filters, contrarian takes, anchored to transcript |
| 2 | `viral-hook-creator` | 5 hooks per idea — 18 proven patterns + trigger words, video-optimized |
| 3 | `creative-director` (quick eval) | Score 1-10, rank, kill weak ideas (< 6), flag #1 pick |
| 4 | `de-ai-ify` | Remove AI patterns, make hooks conversational |

**Config files:** `prompts/ideation_pipeline.md` (instructions), `prompts/creator_context.md` (positioning/ICP)

### Other Available Skills

| Skill | Use during | What it does |
|-------|-----------|-------------|
| `social-content` | Captions | Platform-specific strategy, repurposing frameworks |
| `voice-extractor` | One-time setup | Analyze existing content to capture Cosmo's voice profile |
| `content-strategy` | Planning | Content pillars, gaps, monthly themes |

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-03-29 | Phase 2 — Content Agent upgrade. Classifier engine (`engines/classifier.py`) auto-tags topic, format, and angle. Integrated into orchestrator. 7 /ca-* skills (ca-help, ca-brief, ca-classify, ca-ideate, ca-research, ca-captions, ca-sparring). Knowledge files system (Obsidian vault + local fallback). classify_prompt.md. New `classified` status in Links Queue. |
| 1.3.0 | 2026-03-18 | 4-skill ideation pipeline. Hook 1-5, Score, Top Pick, Filming Setup, Filming Priority fields. Morning Menu sorted by score. Creator context file. |
| 1.2.0 | 2026-03-18 | Generate Ideas status workflow. Triage statuses. Original Caption in ideation prompt. Content Ideas views. Original URL field. |
| 1.1.0 | 2026-03-18 | TikToks/Reels deferred Notion push. YouTube description extraction. TokScript retry logic. Duplicate cleanup. |
| 1.0.0 | 2026-03-18 | Phase 1 MVP complete. All 8 build steps done. |
| 0.1.0 | 2026-03-09 | Original video-pipeline bot with text file storage |
