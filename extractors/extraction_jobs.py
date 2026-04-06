#!/usr/bin/env python3
"""Utilities for listing, inspecting, and completing queued extraction jobs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from extractors.mcp_normalizer import parse_extract_result_output, save_backup, save_raw_output
from extractors.runtime import DEFAULT_BACKUP_DIR, DEFAULT_JOB_DIR


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


def save_job(job_path: Path, job: dict) -> None:
    """Persist a job payload."""
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")


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
