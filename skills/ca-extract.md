---
name: ca-extract
description: Extract transcripts from pending short-form links using TokScript MCP tools
---

Extract transcripts from pending TikTok/Instagram/YouTube links in the Notion Links Queue using TokScript MCP tools — no manual CSV export needed.

## Steps

1. **Query pending links.** Use the Notion MCP to query the Links Queue database (`$NOTION_LINKS_DB_ID`) for all pages with `Status = "pending"`. From each page, extract: `page_id`, `Name`, `Link URL`, and `Category`.

2. **Filter extractable links.** Keep only links where the URL contains `tiktok.com`, `instagram.com/reel`, `youtube.com/shorts`, or `youtube.com/watch`. Skip carousels, LinkedIn, Reddit, X posts. Show the user the list:
   - How many links will be extracted
   - Platform breakdown (TikTok / Instagram / YouTube)
   - Any links skipped and why

3. **Check extraction limits.** Free TokScript tier allows 5 extractions/day. If there are more extractable links than the limit, warn the user and ask which ones to prioritize. Suggest using `get_bulk_transcripts` if available (Pro/Premium only).

4. **Extract transcripts.** For each link, call the appropriate MCP tool:
   - **Instagram:** `mcp__claude_ai_Tokscript__get_instagram_transcript` with `video_url` and `format: "json"`
   - **TikTok:** `mcp__claude_ai_Tokscript__get_tiktok_transcript` with `video_url` and `format: "json"`
   - **YouTube:** `mcp__claude_ai_Tokscript__get_youtube_transcript` with `video_url` and `format: "json"`

   For multiple links, call them in parallel where possible.

5. **Normalize responses.** For each successful MCP response, build a row dict:

   | MCP field | Row key | Transform |
   |-----------|---------|-----------|
   | `title` | `Title` | Use as-is (full caption) |
   | `transcript.segments[].text` | `Transcript` | Join all segment texts with spaces |
   | `views` | `Views` | Convert to string |
   | `duration` | `Duration` | Format as `"{n}s"` |
   | `author.username` | `Author` | Use username string |
   | (from URL) | `Platform` | Detect: `instagram`, `tiktok`, or `youtube` |
   | (from URL) | `URL` | Original link URL |

6. **Update Notion pages.** For each extracted link, update the Notion page using `mcp__claude_ai_Notion__notion-update-page`:
   - Set `Status` to `transcribed`
   - Set `Name` to first 60 chars of title (break at word boundary)
   - Set `Original Caption` to full title (do NOT truncate)
   - Set `Transcript` to joined transcript text (send the FULL transcript, do NOT truncate)
   - Set `Source Views` to views string
   - Set `Duration` to duration string
   - Set `Author` to author username

   If a page doesn't exist for the URL (link was added outside bot), create a new page with the appropriate `Category` set from platform detection.

7. **Save backup.** Run `python -c` to save the extracted data as JSON backup:
   ```
   python -c "
   from extractors.mcp_normalizer import save_backup
   import json, sys
   results = json.loads(sys.argv[1])
   path = save_backup(results)
   print(f'Backup saved: {path}')
   " '<json_array>'
   ```
   Or write the JSON directly to `csv_inbox/mcp_extracts/mcp_extract_<timestamp>.json`.

8. **Report results.** Show a summary:
   - Total extracted: X / Y
   - Per platform: Instagram: N, TikTok: N, YouTube: N
   - Any failures and why
   - Remind: "Run `/ca-classify` to classify the newly transcribed links."

## Error Handling

- If an MCP tool returns an error for a specific link, log it and continue with remaining links. Don't stop the batch.
- If the Notion update fails, report the page name and error. The transcript data is still in the backup JSON.
- If all MCP calls fail, suggest falling back to the CSV workflow: "Export from TokScript web UI and drop the CSV in `csv_inbox/`."
