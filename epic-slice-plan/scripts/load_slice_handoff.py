#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import emit_json, load_handoff, repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load and validate a .pm-dawn slice handoff.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    handoff, paths = load_handoff(root, args.epic_key, args.group_id)
    payload = {
        "repo_root": str(root),
        "slice_markdown_path": str(paths.slice_md),
        "handoff": handoff,
        "handoff_markdown_present": True,
        "handoff_markdown_preview": paths.slice_md.read_text(encoding="utf-8")[:400],
    }
    emit_json(payload)


if __name__ == "__main__":
    main()
