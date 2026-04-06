#!/usr/bin/env python3
"""Shared extractor runtime selection for Claude/Codex-compatible workflows."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from extractors.mcp_normalizer import parse_extract_result_output, save_backup, save_raw_output


PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "csv_inbox" / "mcp_extracts"
DEFAULT_BATCH_SIZE = 10
DEFAULT_BUDGET_USD = 0.50
DEFAULT_MODEL = "sonnet"


@dataclass(frozen=True)
class ExtractorRuntimeConfig:
    agent_runtime: str
    extractor_backend: str
    extractor_model: str
    extractor_batch_size: int
    extractor_budget_usd: float
    claude_cli_path: str | None


def get_runtime_config() -> ExtractorRuntimeConfig:
    """Load extractor runtime configuration from environment variables."""
    agent_runtime = os.getenv("AGENT_RUNTIME", "claude").strip().lower() or "claude"
    extractor_backend = os.getenv("EXTRACTOR_BACKEND", "").strip().lower()
    extractor_model = os.getenv("EXTRACTOR_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    extractor_batch_size = int(os.getenv("EXTRACTOR_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
    extractor_budget_usd = float(os.getenv("EXTRACTOR_BUDGET_USD", str(DEFAULT_BUDGET_USD)))
    claude_cli_path = shutil.which("claude")

    if not extractor_backend:
        extractor_backend = "claude_cli" if agent_runtime == "claude" else "agent_prompt"

    return ExtractorRuntimeConfig(
        agent_runtime=agent_runtime,
        extractor_backend=extractor_backend,
        extractor_model=extractor_model,
        extractor_batch_size=extractor_batch_size,
        extractor_budget_usd=extractor_budget_usd,
        claude_cli_path=claude_cli_path,
    )


def _tool_spec(agent_runtime: str, scope: str) -> tuple[list[str], str]:
    """Return transcript and Notion tool names for the target runtime."""
    if agent_runtime == "codex":
        transcript_tools = {
            "youtube": ["mcp__codex_apps__tokscript_get_youtube_transcript"],
            "shortform": [
                "mcp__codex_apps__tokscript_get_instagram_transcript",
                "mcp__codex_apps__tokscript_get_tiktok_transcript",
                "mcp__codex_apps__tokscript_get_youtube_transcript",
                "mcp__codex_apps__tokscript_get_bulk_transcripts",
            ],
        }
        notion_tool = "mcp__codex_apps__notion_mcp_server_notion_update_page"
    else:
        transcript_tools = {
            "youtube": ["mcp__claude_ai_Tokscript__get_youtube_transcript"],
            "shortform": [
                "mcp__claude_ai_Tokscript__get_instagram_transcript",
                "mcp__claude_ai_Tokscript__get_tiktok_transcript",
                "mcp__claude_ai_Tokscript__get_youtube_transcript",
                "mcp__claude_ai_Tokscript__get_bulk_transcripts",
            ],
        }
        notion_tool = "mcp__claude_ai_Notion__notion-update-page"

    return transcript_tools[scope], notion_tool


def build_extract_worker_prompt(links: list[dict], scope: str, agent_runtime: str) -> str:
    """Build a runtime-specific transcript extraction worker prompt."""
    transcript_tools, notion_tool = _tool_spec(agent_runtime, scope)
    urls_block = "\n".join(
        f"- page_id: {link['page_id']} | url: {link['url']} | name: {link['name'][:60]}"
        for link in links
    )

    if scope == "youtube":
        extraction_instructions = (
            f"1. Call {transcript_tools[0]} with the video URL and format: \"json\".\n"
            "2. From the response, extract: title, author.username, duration, views, "
            "transcript.segments (join all segment texts with spaces)."
        )
    else:
        tool_lines = "\n".join(f"   - {tool}" for tool in transcript_tools)
        extraction_instructions = (
            "1. Detect platform from the URL (instagram, tiktok, or youtube).\n"
            "2. Call the matching transcript tool with the video URL and format: \"json\".\n"
            f"{tool_lines}\n"
            "3. Extract title, author.username, duration, views, and transcript text."
        )

    return f"""You are a transcript extraction worker. Extract transcripts for the following links, then update each Notion page.

## Links to process
{urls_block}

## Runtime
Agent runtime: {agent_runtime}

## Instructions
For each link:
{extraction_instructions}
4. Update the Notion page (use the page_id) via {notion_tool}:
   - Set Status to "transcribed"
   - Set Transcript to all transcript segment texts joined with spaces (send the FULL transcript, do NOT truncate)
   - Set Name to first 60 chars of the title (break at word boundary)
   - Set "Original Caption" to the video description or full title (send full text, do NOT truncate)
   - Set "Source Views" to the view count as a string
   - Set Duration to the duration as a string like "38:06" or "64.9s"
   - Set Author to the author username

Process all links. Call multiple transcript tools in parallel where possible.

After processing all links, output a JSON summary as the LAST line of your response, in this exact format:
EXTRACT_RESULT::{{"extracted": N, "failed": N, "details": [{{"url": "...", "status": "ok"|"error", "title": "...", "error": "..."}}]}}
"""


def _write_prompt_artifacts(
    links: list[dict],
    scope: str,
    prompt: str,
    backup_dir: Path,
    config: ExtractorRuntimeConfig,
) -> Path:
    """Persist an agent-runtime prompt for manual execution."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = save_raw_output(prompt, f"{scope}_{config.agent_runtime}_prompt", backup_dir)
    metadata_path = prompt_path.with_suffix(".json")
    metadata_path.write_text(
        json.dumps(
            {
                "kind": f"{scope}_extract_prompt",
                "agent_runtime": config.agent_runtime,
                "extractor_backend": config.extractor_backend,
                "links": links,
                "prompt_path": str(prompt_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return prompt_path


def run_extraction_backend(
    links: list[dict],
    scope: str,
    *,
    dry_run: bool = False,
    backup_dir: Path | None = None,
    config: ExtractorRuntimeConfig | None = None,
) -> int:
    """Run extraction with the configured backend or emit an agent prompt artifact."""
    if not links:
        return 0

    cfg = config or get_runtime_config()
    target_backup_dir = backup_dir or DEFAULT_BACKUP_DIR
    prompt = build_extract_worker_prompt(links, scope, cfg.agent_runtime)

    if dry_run:
        print(f"  (dry run — would extract {len(links)} link(s) using backend={cfg.extractor_backend} runtime={cfg.agent_runtime})")
        return 0

    if cfg.extractor_backend == "agent_prompt":
        prompt_path = _write_prompt_artifacts(links, scope, prompt, target_backup_dir, cfg)
        print("  Agent prompt backend selected — no subprocess execution")
        print(f"  Prompt saved: {prompt_path}")
        return 0

    if cfg.extractor_backend != "claude_cli":
        print(f"  Unsupported extractor backend: {cfg.extractor_backend}")
        return 0

    if not cfg.claude_cli_path:
        print("  claude CLI not found in PATH — cannot run claude_cli backend")
        return 0

    transcript_tools, notion_tool = _tool_spec("claude", scope)
    cmd = [
        cfg.claude_cli_path,
        "-p", prompt,
        "--model", cfg.extractor_model,
        "--output-format", "text",
        "--max-budget-usd", str(cfg.extractor_budget_usd),
        "--permission-mode", "bypassPermissions",
        "--allowedTools",
        *transcript_tools,
        notion_tool,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        print("  Extraction batch timed out after 10 minutes")
        return 0

    if result.returncode != 0:
        print(f"  Claude CLI exited with code {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:300]}")
        return 0

    output = result.stdout
    raw_backup_path = save_raw_output(output, f"{scope}_extract", target_backup_dir)
    summary = parse_extract_result_output(output, links)
    json_backup_path = save_backup(
        [{
            "kind": f"{scope}_extract",
            "links": links,
            "summary": summary,
            "raw_output_path": str(raw_backup_path),
            "agent_runtime": cfg.agent_runtime,
            "extractor_backend": cfg.extractor_backend,
        }],
        target_backup_dir,
    )

    for detail in summary["details"]:
        status_icon = "ok" if detail["status"] == "ok" else "FAIL"
        title = detail.get("title", detail.get("url", ""))[:50]
        msg = f"    [{status_icon}] {title}"
        if detail.get("error"):
            msg += f" — {detail['error']}"
        print(msg)

    if not summary["parsed"]:
        print("  Could not parse extraction result summary — marked batch as failed in structured backup")
    elif summary["failed"]:
        print(f"  {summary['failed']} link(s) failed — check backup: {json_backup_path}")

    print(f"  Raw backup saved: {raw_backup_path}")
    print(f"  Structured backup saved: {json_backup_path}")
    return summary["extracted"]
