#!/usr/bin/env python3
"""Utilities for listing and inspecting queued extraction jobs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from extractors.runtime import DEFAULT_JOB_DIR


def load_job(job_path: Path) -> dict:
    """Load a single extraction job file."""
    return json.loads(job_path.read_text(encoding="utf-8"))


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


def main() -> None:
    parser = argparse.ArgumentParser(description="List or inspect queued extraction jobs.")
    parser.add_argument("--id", dest="job_id", help="Show a specific job by ID")
    args = parser.parse_args()

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
        print(f"  prompt: {job.get('prompt_path', '')}")
        print(f"  created: {job.get('created_at', '')}")


if __name__ == "__main__":
    main()
