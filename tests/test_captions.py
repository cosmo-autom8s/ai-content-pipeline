"""Tests for engines/captions.py save payload normalization."""

from unittest.mock import patch

from engines.captions import build_caption_properties, normalize_captions_payload, save_captions


def test_normalize_captions_payload_supports_youtube_object():
    payload = normalize_captions_payload({
        "caption_tiktok": "  TikTok hook  ",
        "caption_youtube": {
            "title": "  Useful title  ",
            "description": "  Helpful description.  ",
        },
        "mark_captioned": True,
    })

    assert payload["caption_tiktok"] == "TikTok hook"
    assert payload["caption_youtube"] == "Title: Useful title\n\nDescription: Helpful description."
    assert payload["status"] == "captioned"


def test_normalize_captions_payload_requires_non_empty_caption():
    try:
        normalize_captions_payload({"mark_captioned": True})
    except ValueError as exc:
        assert "at least one" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty caption payload")


def test_build_caption_properties_leaves_status_out_by_default():
    properties = build_caption_properties({"caption_instagram": "IG caption"})
    assert "Caption Instagram" in properties
    assert "Status" not in properties


def test_save_captions_partial_save_keeps_status_unchanged():
    captured = {}

    def fake_patch(url, headers, json, timeout):
        captured["properties"] = json["properties"]

        class Response:
            status_code = 200
            text = ""

        return Response()

    with patch("engines.captions.get_idea_by_id", return_value={"page_id": "abc"}), patch(
        "engines.captions.requests.patch",
        side_effect=fake_patch,
    ):
        result = save_captions("abc", '{"caption_instagram":"IG caption"}')

    assert result is True
    assert "Caption Instagram" in captured["properties"]
    assert "Status" not in captured["properties"]


def test_save_captions_can_set_explicit_status():
    captured = {}

    def fake_patch(url, headers, json, timeout):
        captured["properties"] = json["properties"]

        class Response:
            status_code = 200
            text = ""

        return Response()

    with patch("engines.captions.get_idea_by_id", return_value={"page_id": "abc"}), patch(
        "engines.captions.requests.patch",
        side_effect=fake_patch,
    ):
        result = save_captions("abc", '{"caption_linkedin":"LI caption","status":"captioned"}')

    assert result is True
    assert captured["properties"]["Status"]["select"]["name"] == "captioned"
