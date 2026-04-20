#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import now_iso, read_json, repo_root, run_metadata_path, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mark a .pm-dawn slice run as pending review from the worker side."
    )
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--note", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    path = run_metadata_path(root, args.epic_key, args.group_id)
    if not path.exists():
        raise SystemExit(f"run metadata not found: {path}")

    existing = read_json(path)
    worker = existing.get("worker", {}).copy() if isinstance(existing.get("worker"), dict) else {}
    worker["status"] = "pending_review"
    worker["updated"] = now_iso()
    if args.note:
        worker["note"] = args.note

    existing["status"] = "pending_review"
    existing["last_action"] = "worker_marked_pending_review"
    existing["worker"] = worker
    existing["time"] = {
        "created": existing.get("time", {}).get("created", now_iso()),
        "updated": now_iso(),
    }
    write_json(path, existing)


if __name__ == "__main__":
    main()
