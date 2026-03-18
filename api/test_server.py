"""Tests for the Content Ideas API.

These tests hit the real Notion API (personal tool, not CI).
Run: python -m pytest api/test_server.py -v
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import httpx
from api.server import app

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# /api/ideas
# ---------------------------------------------------------------------------

async def test_list_ideas_returns_list(client):
    resp = await client.get("/api/ideas")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        idea = data[0]
        assert "id" in idea
        assert "name" in idea
        assert "score" in idea
        assert "status" in idea


async def test_filter_by_status(client):
    resp = await client.get("/api/ideas?status=new")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0, "Expected at least one idea with status=new"
    for idea in data:
        assert idea["status"].lower() == "new"


async def test_filter_by_multi_status(client):
    resp = await client.get("/api/ideas?status=new,queued")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0, "Expected at least one idea with status=new or queued"
    for idea in data:
        assert idea["status"].lower() in {"new", "queued"}


async def test_sort_by_score_desc(client):
    resp = await client.get("/api/ideas?sort=score&order=desc")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0, "Expected at least one idea for sort test"
    scores = [i["score"] for i in data if i["score"] is not None]
    assert scores == sorted(scores, reverse=True)
    # None scores must appear at the bottom, not the top
    none_indices = [idx for idx, i in enumerate(data) if i["score"] is None]
    scored_indices = [idx for idx, i in enumerate(data) if i["score"] is not None]
    if none_indices and scored_indices:
        assert min(none_indices) > max(scored_indices), (
            "Ideas with None score should sort to the bottom in desc order"
        )


async def test_search_filter(client):
    # First get any idea name to use as search term
    resp = await client.get("/api/ideas")
    data = resp.json()
    if not data:
        pytest.skip("No ideas in database")
    # Use first word of first idea's name as search term
    term = data[0]["name"].split()[0] if data[0]["name"] else ""
    if not term:
        pytest.skip("First idea has no name")

    resp = await client.get(f"/api/ideas?search={term}")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    for idea in results:
        combined = f"{idea['name']} {idea['main_topic']} {idea['description']}".lower()
        assert term.lower() in combined


async def test_filter_top_picks(client):
    resp = await client.get("/api/ideas?top_pick=true")
    assert resp.status_code == 200
    data = resp.json()
    if not data:
        pytest.skip("No top pick ideas in database")
    for idea in data:
        assert idea["top_pick"] is True


# ---------------------------------------------------------------------------
# /api/ideas/{id}
# ---------------------------------------------------------------------------

async def test_get_idea_detail(client):
    # Get a real idea ID first
    resp = await client.get("/api/ideas")
    data = resp.json()
    if not data:
        pytest.skip("No ideas in database")

    idea_id = data[0]["id"]
    resp = await client.get(f"/api/ideas/{idea_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == idea_id
    assert "hook_1" in detail
    assert "hook_2" in detail
    assert "caption_tiktok" in detail
    assert "post_urls" in detail
    assert isinstance(detail["post_urls"], dict)


async def test_get_idea_invalid_id_returns_404(client):
    resp = await client.get("/api/ideas/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/stats
# ---------------------------------------------------------------------------

async def test_stats_shape(client):
    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "by_status" in data
    assert "top_picks" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["by_status"], dict)
    assert isinstance(data["top_picks"], int)
