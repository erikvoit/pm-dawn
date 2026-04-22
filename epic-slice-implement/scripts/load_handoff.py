#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import emit_json
from pm_dawn_core.implement import load_execution_input
from pm_dawn_core.profile import repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load and validate a .pm-dawn slice handoff.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    handoff, path = load_execution_input(root, args.epic_key, args.group_id, args.packet_id)
    payload = {
        "repo_root": str(root),
        "handoff_path": str(path),
        "handoff": handoff,
    }
    emit_json(payload)


if __name__ == "__main__":
    main()
