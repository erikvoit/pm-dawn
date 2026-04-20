#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import emit_json, load_pr_source, repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load and normalize a Jira-aware PR source from .pm-dawn artifacts.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = load_pr_source(repo_root(args.repo_root), args.epic_key, args.group_id, args.packet_id)
    emit_json(source)


if __name__ == "__main__":
    main()
