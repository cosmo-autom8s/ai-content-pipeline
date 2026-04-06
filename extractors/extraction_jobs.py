#!/usr/bin/env python3
"""Utilities for listing, inspecting, completing, and pruning queued extraction jobs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from extractors.mcp_normalizer import parse_extract_result_output, save_backup, save_raw_output
from extractors.runtime import DEFAULT_BACKUP_DIR, DEFAULT_JOB_DIR

PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
STALE_JOB_DIR = DEFAULT_JOB_DIR / "stale"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)


def notion_headers() -> dict[str, str]:
    """Return Notion API headers from the local environment."""
    api_key = os.getenv("NOTION_API_KEY", "").strip()
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def load_job(job_path: Path) -> dict:
    """Load a single extraction job file."""
    return json.loads(job_path.read_text(encoding="utf-8"))


def find_job_path(job_id: str, job_dir: Path | None = None) -> Path | None:
    """Find a job file by ID."""
    target_dir = job_dir or DEFAULT_JOB_DIR
    job_path = target_dir / f"{job_id}.json"
    return job_path if job_path.exists() else None


def list_jobs(job_dir: Path | None = None) -> list[dict]:
    """Return queued extraction jobs sorted newest first."""
    target_dir = job_dir or DEFAULT_JOB_DIR
    if not target_dir.exists():
        return []

    jobs = []
    for job_path in sorted(target_dir.glob("*.json"), reverse=True):
        job = load_job(job_path)
        job["job_path"] = str(job_path)
        jobs.append(job)
    return jobs


def next_pending_job(job_dir: Path | None = None) -> dict | None:
    """Return the oldest pending job, if any."""
    pending_jobs = [
        job for job in reversed(list_jobs(job_dir))
        if job.get("status", "pending") == "pending"
    ]
    return pending_jobs[0] if pending_jobs else None


def fetch_pending_link_urls() -> set[str]:
    """Return the current set of pending link URLs from the live Notion queue."""
    db_id = os.getenv("NOTION_LINKS_DB_ID", "").strip()
    if not db_id:
        raise EnvironmentError("NOTION_LINKS_DB_ID is not set.")

    urls: set[str] = set()
    has_more = True
    start_cursor: str | None = None
    while has_more:
        body: dict = {
            "page_size": 100,
            "filter": {
                "property": "Status",
                "select": {"equals": "pending"},
            },
        }
        if start_cursor:
            body["start_cursor"] = start_cursor

        response = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=notion_headers(),
            json=body,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()

        for page in payload.get("results", []):
            properties = page.get("properties", {})
            url = properties.get("Link URL", {}).get("url", "").strip()
            if url:
                urls.add(url)

        has_more = payload.get("has_more", False)
        start_cursor = payload.get("next_cursor")

    return urls


def stale_jobs(
    pending_urls: set[str],
    job_dir: Path | None = None,
) -> list[dict]:
    """Return jobs that are no longer represented in the live pending queue."""
    stale: list[dict] = []
    for job in list_jobs(job_dir):
        if job.get("status", "pending") not in {"pending", "in_progress"}:
            continue

        job_urls = {link.get("url", "").strip() for link in job.get("links", []) if link.get("url", "").strip()}
        if job_urls and job_urls.isdisjoint(pending_urls):
            stale.append(job)
    return stale


def save_job(job_path: Path, job: dict) -> None:
    """Persist a job payload."""
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")


def archive_stale_jobs(
    jobs: list[dict],
    *,
    job_dir: Path | None = None,
    archive_dir: Path | None = None,
) -> list[dict]:
    """Move stale jobs into an archive directory and mark them stale."""
    target_job_dir = job_dir or DEFAULT_JOB_DIR
    target_archive_dir = archive_dir or STALE_JOB_DIR
    target_archive_dir.mkdir(parents=True, exist_ok=True)

    archived: list[dict] = []
    for job in jobs:
        job_id = job["job_id"]
        src = find_job_path(job_id, target_job_dir)
        if not src:
            continue

        payload = load_job(src)
        payload["previous_status"] = payload.get("status", "pending")
        payload["status"] = "stale"
        payload["stale_at"] = datetime.now().isoformat(timespec="seconds")
        payload["stale_reason"] = "All linked URLs are absent from the live pending Notion queue."

        dst = target_archive_dir / src.name
        dst.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        src.unlink()
        payload["job_path"] = str(dst)
        archived.append(payload)

    return archived


def claim_job(job_id: str, worker: str, *, job_dir: Path | None = None) -> dict:
    """Mark a pending job as in progress for a named worker."""
    job_path = find_job_path(job_id, job_dir)
    if not job_path:
        raise FileNotFoundError(f"Job not found: {job_id}")

    job = load_job(job_path)
    status = job.get("status", "pending")
    if status not in {"pending", "in_progress"}:
        raise ValueError(f"Cannot claim job in status: {status}")

    job["status"] = "in_progress"
    job["claimed_by"] = worker
    job["claimed_at"] = datetime.now().isoformat(timespec="seconds")
    save_job(job_path, job)
    return job


def release_job(job_id: str, *, job_dir: Path | None = None) -> dict:
    """Release an in-progress job back to pending."""
    job_path = find_job_path(job_id, job_dir)
    if not job_path:
        raise FileNotFoundError(f"Job not found: {job_id}")

    job = load_job(job_path)
    job["status"] = "pending"
    job.pop("claimed_by", None)
    job.pop("claimed_at", None)
    save_job(job_path, job)
    return job


def complete_job_from_output(
    job_id: str,
    output_text: str,
    *,
    job_dir: Path | None = None,
    backup_dir: Path | None = None,
) -> dict:
    """Mark a queued extraction job complete using raw agent output."""
    job_path = find_job_path(job_id, job_dir)
    if not job_path:
        raise FileNotFoundError(f"Job not found: {job_id}")

    job = load_job(job_path)
    summary = parse_extract_result_output(output_text, job.get("links", []))
    raw_output_path = save_raw_output(output_text, f"{job.get('scope', 'extract')}_completed", backup_dir or DEFAULT_BACKUP_DIR)
    structured_backup_path = save_backup(
        [{
            "kind": f"{job.get('scope', 'extract')}_job_completion",
            "job_id": job_id,
            "links": job.get("links", []),
            "summary": summary,
            "raw_output_path": str(raw_output_path),
            "completed_by": job.get("agent_runtime", ""),
        }],
        backup_dir or DEFAULT_BACKUP_DIR,
    )

    job["status"] = "completed" if summary["parsed"] else "failed"
    job["completed_at"] = datetime.now().isoformat(timespec="seconds")
    job.pop("claimed_by", None)
    job.pop("claimed_at", None)
    job["result"] = {
        "parsed": summary["parsed"],
        "extracted": summary["extracted"],
        "failed": summary["failed"],
        "details": summary["details"],
        "raw_output_path": str(raw_output_path),
        "structured_backup_path": str(structured_backup_path),
    }
    save_job(job_path, job)
    return job


def fail_job(job_id: str, error: str, *, job_dir: Path | None = None) -> dict:
    """Mark a queued extraction job failed with an explicit error message."""
    job_path = find_job_path(job_id, job_dir)
    if not job_path:
        raise FileNotFoundError(f"Job not found: {job_id}")

    job = load_job(job_path)
    job["status"] = "failed"
    job["completed_at"] = datetime.now().isoformat(timespec="seconds")
    job.pop("claimed_by", None)
    job.pop("claimed_at", None)
    job["result"] = {
        "parsed": False,
        "extracted": 0,
        "failed": len(job.get("links", [])),
        "details": [],
        "error": error,
    }
    save_job(job_path, job)
    return job


def main() -> None:
    parser = argparse.ArgumentParser(description="List, inspect, or complete queued extraction jobs.")
    parser.add_argument("--id", dest="job_id", help="Show a specific job by ID")
    parser.add_argument("--next", action="store_true", help="Show the next pending job")
    parser.add_argument("--claim", dest="claim_job_id", help="Claim a job for a worker")
    parser.add_argument("--worker", dest="worker_name", help="Worker name for --claim")
    parser.add_argument("--release", dest="release_job_id", help="Release an in-progress job back to pending")
    parser.add_argument("--stale", action="store_true", help="List jobs that are stale relative to the live pending Notion queue")
    parser.add_argument("--prune-stale", action="store_true", help="Archive stale jobs into extraction_jobs/stale/")
    parser.add_argument("--complete", dest="complete_job_id", help="Mark a job completed from agent output")
    parser.add_argument("--output-file", dest="output_file", help="Path to raw agent output text for --complete")
    parser.add_argument("--fail", dest="fail_job_id", help="Mark a job failed")
    parser.add_argument("--error", dest="error_message", help="Error message for --fail")
    args = parser.parse_args()

    if args.next:
        job = next_pending_job()
        if not job:
            print("No pending extraction jobs.")
            return
        print(json.dumps(job, indent=2))
        return

    if args.claim_job_id:
        if not args.worker_name:
            print("--claim requires --worker")
            return
        job = claim_job(args.claim_job_id, args.worker_name)
        print(json.dumps(job, indent=2))
        return

    if args.release_job_id:
        job = release_job(args.release_job_id)
        print(json.dumps(job, indent=2))
        return

    if args.stale or args.prune_stale:
        pending_urls = fetch_pending_link_urls()
        jobs = stale_jobs(pending_urls)
        if args.prune_stale:
            archived = archive_stale_jobs(jobs)
            print(json.dumps({
                "archived": len(archived),
                "jobs": archived,
            }, indent=2))
            return
        print(json.dumps({
            "stale": len(jobs),
            "jobs": jobs,
        }, indent=2))
        return

    if args.complete_job_id:
        if not args.output_file:
            print("--complete requires --output-file")
            return
        output_path = Path(args.output_file)
        if not output_path.exists():
            print(f"Output file not found: {output_path}")
            return
        job = complete_job_from_output(args.complete_job_id, output_path.read_text(encoding="utf-8"))
        print(json.dumps(job, indent=2))
        return

    if args.fail_job_id:
        if not args.error_message:
            print("--fail requires --error")
            return
        job = fail_job(args.fail_job_id, args.error_message)
        print(json.dumps(job, indent=2))
        return

    jobs = list_jobs()
    if args.job_id:
        for job in jobs:
            if job.get("job_id") == args.job_id:
                print(json.dumps(job, indent=2))
                return
        print(f"Job not found: {args.job_id}")
        return

    if not jobs:
        print("No extraction jobs queued.")
        return

    print(f"{len(jobs)} extraction job(s) queued:\n")
    for job in jobs:
        print(f"- {job['job_id']} [{job.get('status', 'unknown')}]")
        print(f"  scope: {job.get('scope', '')}")
        print(f"  runtime: {job.get('agent_runtime', '')}")
        print(f"  links: {len(job.get('links', []))}")
        if job.get("claimed_by"):
            print(f"  claimed by: {job['claimed_by']} at {job.get('claimed_at', '')}")
        print(f"  prompt: {job.get('prompt_path', '')}")
        print(f"  created: {job.get('created_at', '')}")


if __name__ == "__main__":
    main()
