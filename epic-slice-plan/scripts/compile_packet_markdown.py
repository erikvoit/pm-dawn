#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import emit_json, repo_root, write_json
from pm_dawn_core.implement import compile_packet_handoff


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile one packet Markdown artifact into execution JSON.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("packet_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    payload, default_output = compile_packet_handoff(root, args.epic_key, args.group_id, args.packet_id)
    if args.output:
        output_path = Path(args.output).resolve()
        write_json(output_path, payload)
    else:
        write_json(default_output, payload)
    emit_json(payload)


if __name__ == "__main__":
    main()
