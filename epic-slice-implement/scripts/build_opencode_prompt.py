#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.implement import (
    build_launch_prompt,
    build_steer_prompt,
    load_execution_input,
    resolve_approved_plan_path,
    resolve_implement_command,
)
from pm_dawn_core.profile import repo_root


def parse_args() -> argparse.Namespace:
    surface = resolve_implement_command("prompt")
    parser = argparse.ArgumentParser(description=surface.description)
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
        approved_plan = resolve_approved_plan_path(root, args.epic_key, args.packet_id, args.approved_plan)
        prompt = build_launch_prompt(handoff, handoff_path, root, phase=args.phase, approved_plan_path=approved_plan)
    sys.stdout.write(prompt)
    if not prompt.endswith("\n"):
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
