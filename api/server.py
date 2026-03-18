"""FastAPI server for Content Ideas Dashboard.

Thin proxy to Notion with filtering/sorting in Python.
Serves the built React frontend as static files when available.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

import api.notion as notion

app = FastAPI()


# ---------------------------------------------------------------------------
# API routes (registered BEFORE static files)
# ---------------------------------------------------------------------------

@app.get("/api/stats")
async def get_stats():
    """Return idea statistics: total, by_status, top_picks."""
    return await notion.get_ideas_stats()


@app.get("/api/ideas")
async def list_ideas(
    status: str | None = None,
    sort: str = "score",
    order: str = "desc",
    filming_setup: str | None = None,
    format: str | None = None,
    top_pick: str | None = None,
    search: str | None = None,
):
    """List all ideas with optional filtering and sorting."""
    ideas = await notion.query_all_ideas()

    # 1. Status filter (comma-separated)
    if status:
        allowed = {s.strip().lower() for s in status.split(",")}
        ideas = [i for i in ideas if (i["status"] or "").lower() in allowed]

    # 2. Filming setup filter
    if filming_setup:
        ideas = [
            i for i in ideas
            if filming_setup.lower() in [s.lower() for s in i["filming_setup"]]
        ]

    # 3. Format filter
    if format:
        ideas = [
            i for i in ideas
            if i["format"] and i["format"].lower() == format.lower()
        ]

    # 4. Top pick filter
    if top_pick and top_pick.lower() == "true":
        ideas = [i for i in ideas if i["top_pick"]]

    # 5. Search filter (case-insensitive on name, main_topic, description)
    if search:
        q = search.lower()
        ideas = [
            i for i in ideas
            if q in (i["name"] or "").lower()
            or q in (i["main_topic"] or "").lower()
            or q in (i["description"] or "").lower()
        ]

    # 6. Sort
    sort_key = sort.lower()
    reverse = order.lower() == "desc"

    def _sort_value(idea: dict):
        val = idea.get(sort_key)
        if val is None:
            # Push None values to the end regardless of sort order
            return (1, "")
        if isinstance(val, bool):
            return (0, val)
        if isinstance(val, (int, float)):
            return (0, val)
        return (0, str(val).lower())

    ideas.sort(key=_sort_value, reverse=reverse)

    return ideas


@app.get("/api/ideas/{idea_id}")
async def get_idea(idea_id: str):
    """Get full detail for a single idea."""
    idea = await notion.get_idea_detail(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


# ---------------------------------------------------------------------------
# Static file serving (built React app)
# ---------------------------------------------------------------------------

frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(frontend_dist / "index.html")
