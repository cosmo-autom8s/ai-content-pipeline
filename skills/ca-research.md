---
name: ca-research
description: Research a topic for content angles — search web, save findings to knowledge files
---

Research a topic to uncover content angles Cosmo can actually film.

## Steps

1. **Get the topic.** If the user didn't provide one, ask: "What topic do you want to research?" Do not proceed without a topic.

2. **Search broadly.** Use web search and web fetch to find:
   - Articles, blog posts, and guides on the topic
   - Tools and products related to the topic
   - GitHub repos if technically relevant
   - Trending discussions on Reddit, X (Twitter), and Hacker News

3. **Organize findings into four sections:**

   ### Key Findings
   Top 3–5 insights worth knowing — focus on non-obvious takeaways, not summaries of the obvious.

   ### Tools Discovered
   Any tools, products, or services worth tracking. Name, what it does, why it matters.

   ### Content Angles
   3–5 specific video ideas Cosmo could film from this research. Be concrete — not "cover this topic" but "here's the exact angle nobody else is covering and why it would land."

   ### Sources
   Links to everything found during research.

4. **Offer to save findings.** After presenting, ask: "Want to save any of this to your knowledge files?" Map findings to the right file:
   - Tools → append to `$OBSIDIAN_VAULT_PATH/content/tool-library.md` (fallback: `knowledge/tool-library.md`)
   - Lessons or principles → append to `content-principles.md`
   - Ideas → append to `idea-backlog.md`

   Use this format when appending:
   ```
   ## Title

   Content

   **Source:** source name
   **Source URL:** url
   ```

5. **Voice and standards.** Stay direct — no fluff, no padding. Don't recap what the user already knows. Find the angles nobody else is covering. Every output should answer: "What can you FILM from this research?"
