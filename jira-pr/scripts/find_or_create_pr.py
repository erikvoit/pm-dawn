#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import emit_json, find_existing_pr, load_pr_source, read_text, repo_root, run_cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find an existing PR for the current branch or create one.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--title-file", required=True)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--base", default="main")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    source = load_pr_source(root, args.epic_key, args.group_id, args.packet_id)
    existing = find_existing_pr(root, source["current_branch"], args.pr_number)
    if existing:
        payload = {"action": "existing", "pr": existing}
        emit_json(payload)
        return

    cmd = [
        "gh",
        "pr",
        "create",
        "--base",
        args.base,
        "--head",
        source["current_branch"],
        "--title",
        read_text(repo_root(args.title_file)).strip(),
        "--body-file",
        str(repo_root(args.body_file)),
    ]
    if args.dry_run:
        emit_json({"action": "create", "dry_run": True, "command": cmd})
        return
    run_cmd(cmd, cwd=root)
    created = find_existing_pr(root, source["current_branch"])
    emit_json({"action": "create", "dry_run": False, "pr": created})


if __name__ == "__main__":
    main()
