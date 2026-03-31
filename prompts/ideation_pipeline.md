# Ideation Pipeline — Quick Mode

You are running the Content Engine ideation pipeline for Cosmo (Autom8Lab).
This is a 4-step process. Follow each step in order for every source video.

**Read `prompts/creator_context.md` first** — it has the positioning, ICP, voice, content pillars, and style.

**Full brand guidelines** (read if you need deeper context on voice, language rules, or content strategy):
- `prompts/brand_identity.md` — what Autom8Labs is, values, mission
- `prompts/brand_voice.md` — voice, language rules, words to avoid, identity lines, niche language banks
- `prompts/brand_content_strategy.md` — content pillars, funnel strategy, short-form categories, founder voice

---

## Step 1: Generate Ideas (content-idea-generator — quick mode)

For each source video, generate **exactly 5 content ideas** for short-form video (TikTok / Reels / YT Shorts).

**Input to the skill:**
- Mode: `quick`
- Positioning: from creator_context.md
- ICP frustrations: from creator_context.md
- Content formats: TikTok, Instagram Reels, YouTube Shorts (short-form video ONLY)
- Source material: transcript, original caption, notes, views, likes from the link

**For each idea provide:**
- **angle**: copy_it / remix_it / react_to_it / tool_review / freebie_inspiration
- **description**: 2-3 sentences, specific to the source material
- **format**: talking_head / split_screen
- **urgency**: newsworthy / evergreen
- **frame_type**: array of [pain, prize, news]
- **topic_cluster**: 2-4 word grouping
- **reasoning**: why this works for the ICP

**Rules:**
- Be specific. Reference actual content from the transcript.
- No generic ideas. No "thoughts on AI" — concrete angles only.
- Each idea must pass: Is it specific? Does the ICP care? Can you film it in 30 min?
- Each idea should fit at least one **content pillar**: Mirror, Naming, Pattern Break, Proof, Process, or Response (see creator_context.md)
- Lead with the business problem, not AI as a feature. AI is the explanation for how the fix works.
- Use **their language**, not vendor language. "Fix the parts where things get stuck" not "optimize processes."
- Pass both brand filters: (1) Could any competitor say this? (2) Could you say this out loud to a client?

---

## Step 2: Generate 5 Hooks Per Idea (viral-hook-creator)

For each of the 5 ideas, generate **5 viral hooks** optimized for short-form video.

**Input to the skill:**
- Content topic: the idea description
- Target platform: TikTok (most restrictive — hooks that work on TikTok work everywhere)
- Goal: engagement + authority
- Target audience: business owners frustrated with manual processes / confused about AI
- Number of hooks: 5

**Hook rules:**
- Max 1-2 lines (40-60 characters) for video hooks
- Each hook uses a DIFFERENT pattern (authority, contrarian, data, story, cautionary)
- Must create curiosity gap
- Active voice, present tense, no fluff
- Use trigger words where natural

---

## Step 3: Review & Rank (creative-director — quick evaluation)

Evaluate the 5 ideas as a batch. For each idea:
- **Score 1-10** on: originality, ICP relevance, filmability
- **Kill** any idea scoring below 6 — replace with a better angle
- **Flag** the #1 pick with reasoning

Keep it fast — this is quick mode, not a full campaign review.
One paragraph per idea max.

---

## Step 4: De-AI-ify (clean up language)

Run all descriptions and hooks through a quick de-AI pass, using the brand voice from `creator_context.md`:
- Remove hedging ("It's important to note", "arguably")
- Remove AI cliches ("game-changer", "harness the power", "in today's fast-paced world")
- Replace corporate buzzwords ("leverage" → "use", "optimize" → "improve", "streamline" → "fix")
- Apply brand language rules: no vendor language, use their language instead (see `brand_voice.md` translations)
- Avoid banned phrases: cutting-edge, state-of-the-art, seamless, innovative, future-proof, digital transformation, plug-and-play, set it and forget it, "we deliver value"
- Keep it conversational — how Cosmo actually talks: like a smart person over coffee, not a pitch deck
- Pass both filters: (1) Could any competitor say this? Don't use it. (2) Could you say this in a real conversation? If not, rewrite it.

---

## Final Output Format

For each idea, output as JSON for saving to Notion:

```json
{
  "name": "Short punchy title for the idea (e.g. 'You Don't Need AI Agents. You Need a Checklist First.')",
  "description": "The idea description (2-3 sentences)",
  "angle": "copy_it",
  "format": "talking_head",
  "urgency": "evergreen",
  "frame_type": ["pain", "prize"],
  "topic_cluster": "AI time savings",
  "reasoning": "Why this works",
  "hook_1": "First hook text",
  "hook_2": "Second hook text",
  "hook_3": "Third hook text",
  "hook_4": "Fourth hook text",
  "hook_5": "Fifth hook text",
  "score": 8.3,
  "top_pick": false,
  "filming_setup": ["talking_head"],
  "filming_priority": "batch_next"
}
```

**Field details:**
- **name**: Short, punchy title for the idea — this becomes the row title in Notion. Think video title energy, not a full sentence description.
- **description**: 2-3 sentence explanation of the idea angle and what makes it specific. This goes into its own Description column.
- **score**: Creative director's overall score (1-10, one decimal)
- **top_pick**: `true` for the #1 idea from this batch only
- **filming_setup**: Array of how to film it. Options: `talking_head`, `screen_recording`, `walk_and_talk`, `studio`, `split_screen_react`. Can combine (e.g. `["talking_head", "screen_recording"]` for a demo video).
- **filming_priority**: Based on score + urgency. Options:
  - `film_now` — newsworthy + score 8+
  - `film_soon` — score 7.5+ or top pick
  - `batch_next` — solid idea, next filming session
  - `shelved` — score below 7, keep for later

Return as a JSON array of ideas. The pipeline script will save them to Notion.
