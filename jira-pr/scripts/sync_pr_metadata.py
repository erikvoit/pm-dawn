#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import emit_json, find_existing_pr, load_pr_source, read_text, repo_root, run_cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch an existing PR title/body to the canonical generated content.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--title-file", required=True)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    source = load_pr_source(root, args.epic_key, args.group_id, args.packet_id)
    pr = find_existing_pr(root, source["current_branch"], args.pr_number)
    if not pr:
        raise SystemExit("no existing PR found to sync")
    cmd = [
        "gh",
        "pr",
        "edit",
        str(pr["number"]),
        "--title",
        read_text(repo_root(args.title_file)).strip(),
        "--body-file",
        str(repo_root(args.body_file)),
    ]
    if args.dry_run:
        emit_json({"action": "sync", "dry_run": True, "pr": pr, "command": cmd})
        return
    run_cmd(cmd, cwd=root)
    refreshed = find_existing_pr(root, source["current_branch"], pr["number"])
    emit_json({"action": "sync", "dry_run": False, "pr": refreshed})


if __name__ == "__main__":
    main()
