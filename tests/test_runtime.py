"""Tests for shared extractor runtime configuration and prompt generation."""

from unittest.mock import patch

from pathlib import Path
from tempfile import TemporaryDirectory

from extractors.runtime import build_extract_worker_prompt, create_extraction_job, get_runtime_config


def test_get_runtime_config_defaults_to_claude_cli_for_claude_runtime():
    with patch("extractors.runtime.os.getenv", side_effect=lambda key, default="": {
        "AGENT_RUNTIME": "claude",
        "EXTRACTOR_BACKEND": "",
        "EXTRACTOR_MODEL": "sonnet",
        "EXTRACTOR_BATCH_SIZE": "10",
        "EXTRACTOR_BUDGET_USD": "0.5",
    }.get(key, default)), patch("extractors.runtime.shutil.which", return_value="/usr/local/bin/claude"):
        config = get_runtime_config()

    assert config.agent_runtime == "claude"
    assert config.extractor_backend == "claude_cli"
    assert config.claude_cli_path == "/usr/local/bin/claude"


def test_get_runtime_config_defaults_to_agent_prompt_for_codex_runtime():
    with patch("extractors.runtime.os.getenv", side_effect=lambda key, default="": {
        "AGENT_RUNTIME": "codex",
        "EXTRACTOR_BACKEND": "",
        "EXTRACTOR_MODEL": "sonnet",
        "EXTRACTOR_BATCH_SIZE": "10",
        "EXTRACTOR_BUDGET_USD": "0.5",
    }.get(key, default)), patch("extractors.runtime.shutil.which", return_value=None):
        config = get_runtime_config()

    assert config.agent_runtime == "codex"
    assert config.extractor_backend == "agent_prompt"


def test_build_extract_worker_prompt_uses_codex_tool_names():
    prompt = build_extract_worker_prompt(
        [{"page_id": "abc", "url": "https://youtu.be/12345678901", "name": "Video"}],
        "youtube",
        "codex",
    )

    assert "mcp__codex_apps__tokscript_get_youtube_transcript" in prompt
    assert "mcp__codex_apps__notion_mcp_server_notion_update_page" in prompt


def test_build_extract_worker_prompt_uses_claude_tool_names():
    prompt = build_extract_worker_prompt(
        [{"page_id": "abc", "url": "https://tiktok.com/@x/video/1", "name": "Video"}],
        "shortform",
        "claude",
    )

    assert "mcp__claude_ai_Tokscript__get_tiktok_transcript" in prompt
    assert "mcp__claude_ai_Notion__notion-update-page" in prompt


def test_create_extraction_job_writes_pending_job_file():
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        backup_dir = base / "backups"
        job_dir = base / "jobs"
        config = get_runtime_config()
        job_path = create_extraction_job(
            [{"page_id": "abc", "url": "https://youtu.be/12345678901", "name": "Video"}],
            "youtube",
            "prompt text",
            config,
            backup_dir=backup_dir,
            job_dir=job_dir,
        )

        payload = job_path.read_text(encoding="utf-8")
        assert job_path.exists()
        assert "\"status\": \"pending\"" in payload
        assert "\"scope\": \"youtube\"" in payload
