---
name: ca-classify
description: Run the classifier on transcribed links — auto-tag and extract insights
---

Run the classifier on transcribed links to auto-tag content and extract insights.

## Steps

1. **Dry run first.** Run `python engines/classifier.py --dry-run` to show what would be classified without making any changes. Display the list of links that would be processed, along with the tags that would be applied to each.

2. **Ask for confirmation.** Show the user the dry-run results and ask: "Ready to classify all of these, or do you want to pick specific links?" If they specify links, pass them as arguments to the classifier.

3. **Run the classifier.** On confirmation, run `python engines/classifier.py` (or with specific link IDs if the user selected a subset).

4. **Show results summary.** After the run completes, report:
   - How many links were classified
   - What tags were applied (and how many times each)
   - Any links that failed or were skipped

5. **Offer tag adjustments.** If the user disagrees with any classification, offer to adjust tags directly via Notion MCP. Ask them to specify which link and what tags they'd prefer, then update accordingly.

6. **Retry errors flag.** If the user says "retry errors" or asks to retry failed links, run with the `--retry-errors` flag: `python engines/classifier.py --retry-errors`.

7. **Remind about Notion view.** After classification is complete, remind the user: "You can review all classified links in the Notion 'Classified' view to verify the results or make further edits."
