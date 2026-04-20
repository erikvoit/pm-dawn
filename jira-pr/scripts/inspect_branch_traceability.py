#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import emit_json, inspect_branch_traceability, load_project_profile, load_pr_source, repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect current branch and commit traceability for Jira-aligned PRs.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    profile = load_project_profile(root)
    source = load_pr_source(root, args.epic_key, args.group_id, args.packet_id)
    emit_json(inspect_branch_traceability(root, source, profile))


if __name__ == "__main__":
    main()
