from extractors.mcp_normalizer import parse_extract_result_output


def test_parse_extract_result_output_parses_summary():
    links = [{"url": "https://example.com/1", "name": "Video 1"}]
    output = """
Some worker output
EXTRACT_RESULT::{"extracted": 1, "failed": 0, "details": [{"url": "https://example.com/1", "status": "ok", "title": "Video 1"}]}
""".strip()

    result = parse_extract_result_output(output, links)

    assert result["parsed"] is True
    assert result["extracted"] == 1
    assert result["failed"] == 0
    assert result["details"][0]["status"] == "ok"


def test_parse_extract_result_output_normalizes_missing_fields():
    links = [{"url": "https://example.com/1", "name": "Video 1"}]
    output = """
EXTRACT_RESULT::{"details": [{"url": "https://example.com/1", "status": "error", "error": "timeout"}]}
""".strip()

    result = parse_extract_result_output(output, links)

    assert result["parsed"] is True
    assert result["extracted"] == 0
    assert result["failed"] == 1
    assert result["details"][0]["title"] == "https://example.com/1"
    assert result["details"][0]["error"] == "timeout"


def test_parse_extract_result_output_fails_closed_without_summary():
    links = [
        {"url": "https://example.com/1", "name": "Video 1"},
        {"url": "https://example.com/2", "name": "Video 2"},
    ]
    output = "worker printed text but never emitted a summary line"

    result = parse_extract_result_output(output, links)

    assert result["parsed"] is False
    assert result["extracted"] == 0
    assert result["failed"] == 2
    assert result["details"][0]["status"] == "unknown"
    assert result["details"][0]["error"] == "missing EXTRACT_RESULT summary"
