#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import emit_json, repo_root
from pm_dawn_core.plan import load_slice_handoff_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load and validate a .pm-dawn slice handoff.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    emit_json(load_slice_handoff_payload(root, args.epic_key, args.group_id))


if __name__ == "__main__":
    main()
