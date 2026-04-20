#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import build_launch_prompt, build_steer_prompt, load_execution_input, repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the exact opencode prompt for a .pm-dawn slice.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=("launch", "steer"), default="launch")
    parser.add_argument("--phase", choices=("planning", "implementing"), default="implementing")
    parser.add_argument("--approved-plan")
    parser.add_argument("--steering-message")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    handoff, handoff_path = load_execution_input(root, args.epic_key, args.group_id, args.packet_id)
    if args.mode == "steer":
        if not args.steering_message:
            raise SystemExit("--steering-message is required for steer mode")
        prompt = build_steer_prompt(handoff, handoff_path, root, args.steering_message)
    else:
        approved_plan = Path(args.approved_plan).resolve() if args.approved_plan else None
        prompt = build_launch_prompt(handoff, handoff_path, root, phase=args.phase, approved_plan_path=approved_plan)
    sys.stdout.write(prompt)
    if not prompt.endswith("\n"):
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
