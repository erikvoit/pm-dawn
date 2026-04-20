#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import emit_json, find_existing_pr, load_project_profile, load_pr_source, repo_root, verify_live_pr, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify that a live PR body preserves required Jira traceability.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    profile = load_project_profile(root)
    source = load_pr_source(root, args.epic_key, args.group_id, args.packet_id)
    pr = find_existing_pr(root, source["current_branch"], args.pr_number)
    if not pr:
        raise SystemExit("no live PR found for verification")
    blocking_errors, warnings = verify_live_pr(source, pr, source["title"], profile)
    payload = {
        "epic_key": args.epic_key,
        "group_id": args.group_id,
        "packet_id": args.packet_id,
        "pr_number": pr["number"],
        "ready": not blocking_errors,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "pr": pr,
    }
    write_json(repo_root(source["verify_path"]), payload)
    emit_json(payload)
    if blocking_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
