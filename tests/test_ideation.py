"""Tests for engines/ideation.py validation and deduplication."""

from unittest.mock import patch

from engines.ideation import (
    find_duplicate_idea,
    normalize_idea,
    save_ideas,
)


def test_normalize_idea_accepts_and_cleans_fields():
    idea = normalize_idea({
        "name": "  Fast Hook  ",
        "description": "  Explain why the hook works.  ",
        "reasoning": "  This is specific. ",
        "hook_1": " First hook ",
        "frame_type": "pain,prize,bad_frame",
        "filming_setup": "talking_head,studio,invalid",
        "score": "9.5",
        "top_pick": 1,
    })

    assert idea["name"] == "Fast Hook"
    assert idea["description"] == "Explain why the hook works."
    assert idea["reasoning"] == "This is specific."
    assert idea["hook_1"] == "First hook"
    assert idea["frame_type"] == ["pain", "prize"]
    assert idea["filming_setup"] == ["talking_head", "studio"]
    assert idea["score"] == 9.5
    assert idea["top_pick"] is True


def test_normalize_idea_requires_description():
    try:
        normalize_idea({"name": "Missing description"})
    except ValueError as exc:
        assert "missing description" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing description")


def test_find_duplicate_idea_matches_name_and_description():
    duplicate = find_duplicate_idea(
        {"name": "Fast Hook", "description": "Explain the pattern."},
        [{"name": " fast hook ", "description": " explain the pattern. "}],
    )
    assert duplicate is not None


def test_save_ideas_skips_invalid_and_duplicate_items():
    ideas_json = """
    [
      {"name": "Existing", "description": "Already saved"},
      {"name": "Invalid"},
      {"name": "Fresh", "description": "A new idea", "score": 8}
    ]
    """

    created = []

    with patch("engines.ideation.get_link_by_id", return_value={"page_id": "abc", "url": "https://source"}), patch(
        "engines.ideation.query_existing_ideas",
        return_value=[{"name": "existing", "description": "already saved"}],
    ), patch("engines.ideation.create_idea_in_notion", side_effect=lambda idea, *_: created.append(idea) or True), patch(
        "engines.ideation.mark_link_processed",
        return_value=True,
    ) as mark_processed:
        saved = save_ideas(ideas_json, "abc", "https://source")

    assert saved == 1
    assert len(created) == 1
    assert created[0]["name"] == "Fresh"
    mark_processed.assert_called_once_with("abc")
