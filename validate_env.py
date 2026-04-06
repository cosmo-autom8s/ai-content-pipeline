#!/usr/bin/env python3
"""Validate local environment and service connectivity for the content pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).parent
ENV_PATH = PROJECT_ROOT / ".env"

REQUIRED_ENV_VARS = [
    "NOTION_API_KEY",
    "NOTION_LINKS_DB_ID",
    "NOTION_IDEAS_DB_ID",
    "OPENROUTER_API_KEY",
    "OBSIDIAN_VAULT_PATH",
]

OPTIONAL_ENV_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_CHAT_IDS",
    "CLASSIFIER_MODEL",
    "CLASSIFIER_DELAY",
    "YOUTUBE_COOKIES_B64",
]


def _checkmark(ok: bool) -> str:
    return "OK" if ok else "FAIL"


def load_env() -> None:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)


def validate_env_vars() -> tuple[list[str], list[str]]:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name, "").strip()]
    present_optional = [name for name in OPTIONAL_ENV_VARS if os.getenv(name, "").strip()]
    return missing, present_optional


def validate_obsidian_path() -> tuple[bool, str]:
    vault_root = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault_root:
        return False, "OBSIDIAN_VAULT_PATH is missing"

    content_dir = Path(vault_root) / "content"
    if not content_dir.exists():
        return False, f"content directory not found: {content_dir}"

    md_files = list(content_dir.glob("*.md"))
    return True, f"{content_dir} ({len(md_files)} markdown files)"


def validate_notion() -> tuple[bool, str]:
    api_key = os.getenv("NOTION_API_KEY", "").strip()
    db_ids = {
        "links": os.getenv("NOTION_LINKS_DB_ID", "").strip(),
        "ideas": os.getenv("NOTION_IDEAS_DB_ID", "").strip(),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    results = []
    for name, db_id in db_ids.items():
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=headers,
            json={"page_size": 1},
            timeout=20,
        )
        if resp.status_code != 200:
            return False, f"{name} DB query failed ({resp.status_code})"
        payload = resp.json()
        results.append(f"{name}:{len(payload.get('results', []))} row sample")

    return True, ", ".join(results)


def validate_openrouter() -> tuple[bool, str]:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("CLASSIFIER_MODEL", "qwen/qwen3.6-plus:free").strip()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
        "max_tokens": 5,
    }
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=30,
    )

    if resp.status_code == 200:
        return True, f"chat completion succeeded for {model}"
    if resp.status_code == 429:
        return True, f"authenticated, provider rate-limited for {model}"
    if resp.status_code in {401, 403}:
        return False, f"authentication failed ({resp.status_code})"
    return False, f"unexpected status {resp.status_code}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate local environment and service connectivity.",
    )
    parser.add_argument(
        "--skip-network",
        action="store_true",
        help="Only validate local environment and filesystem paths.",
    )
    args = parser.parse_args()

    load_env()

    print("Content Pipeline Environment Validation")
    print("=" * 40)

    if not ENV_PATH.exists():
        print("[FAIL] .env file is missing")
        print("Copy .env.example to .env and fill in the required values.")
        return 1

    missing, present_optional = validate_env_vars()
    if missing:
        print(f"[FAIL] Required env vars missing: {', '.join(missing)}")
    else:
        print("[OK] Required env vars present")

    if present_optional:
        print(f"[OK] Optional env vars present: {', '.join(present_optional)}")
    else:
        print("[OK] No optional env vars configured")

    obsidian_ok, obsidian_msg = validate_obsidian_path()
    print(f"[{_checkmark(obsidian_ok)}] Obsidian: {obsidian_msg}")

    network_failures = 0
    if not args.skip_network and not missing:
        notion_ok, notion_msg = validate_notion()
        print(f"[{_checkmark(notion_ok)}] Notion: {notion_msg}")
        network_failures += 0 if notion_ok else 1

        openrouter_ok, openrouter_msg = validate_openrouter()
        print(f"[{_checkmark(openrouter_ok)}] OpenRouter: {openrouter_msg}")
        network_failures += 0 if openrouter_ok else 1
    elif args.skip_network:
        print("[OK] Skipped network validation by request")
    else:
        print("[FAIL] Network validation skipped because required env vars are missing")
        network_failures += 1

    print("[OK] MCP note: TokScript/Notion MCP access must be validated from the active agent session.")

    failures = len(missing) + (0 if obsidian_ok else 1) + network_failures
    print()
    print(f"Result: {'PASS' if failures == 0 else 'FAIL'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
