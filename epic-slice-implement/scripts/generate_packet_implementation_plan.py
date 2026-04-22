#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import (
    check_active_harness_model,
    emit_json,
    repo_root,
)
from harness_opencode import run_packet_planning as run_opencode_packet_planning
from harness_pi import run_packet_planning as run_pi_packet_planning
from pm_dawn_core.implement import (
    implementation_plan_artifact_path,
    packet_markdown_path,
    render_implement_command,
    resolve_agent_harness,
    resolve_harness_model,
    resolve_implement_command,
)


def parse_args() -> argparse.Namespace:
    surface = resolve_implement_command("plan")
    parser = argparse.ArgumentParser(
        description=surface.description,
    )
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("packet_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--harness")
    parser.add_argument("--model")
    parser.add_argument("--title")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    harness = resolve_agent_harness(
        root,
        explicit_harness=args.harness,
        phase="planning",
    )
    model = resolve_harness_model(
        root,
        harness=harness,
        explicit_model=args.model,
        phase="planning",
        packet_id=args.packet_id,
    )
    model_check = check_active_harness_model(harness, model)
    packet_path = packet_markdown_path(root, args.epic_key, args.packet_id)
    output_path = implementation_plan_artifact_path(root, args.epic_key, args.packet_id)

    if not packet_path.exists():
        raise SystemExit(f"packet Markdown not found: {packet_path}")

    title = args.title or f"packet-plan:{args.epic_key}:{args.packet_id}"
    reviewed_artifact_command = render_implement_command(
        root,
        "plan",
        args.epic_key,
        args.group_id,
        args.packet_id,
        "--repo-root",
        ".",
    )
    prompt = (
        "Use the packet-implementation-plan skill. "
        f"Read {packet_path} and produce the implementation plan only. "
        f"Write it to {output_path}. "
        "Do not edit code, do not switch branches, and do not implement the packet. "
        "This run is not successful unless the plan file exists at the required path when you finish. "
        f"The canonical PM Dawn command surface for this action is: {reviewed_artifact_command}"
    )

    if harness == "pi":
        session_dir = (
            root
            / ".pm-dawn"
            / "epics"
            / args.epic_key
            / "ops"
            / "runs"
            / "pi-sessions"
            / args.packet_id
            / "planning"
        )
        run_pi_packet_planning(
            root=root,
            epic_key=args.epic_key,
            packet_id=args.packet_id,
            model=model,
            prompt=prompt,
            output_path=output_path,
            model_check=model_check,
            packet_path=packet_path,
            session_dir=session_dir,
        )
    else:
        run_opencode_packet_planning(
            root=root,
            epic_key=args.epic_key,
            packet_id=args.packet_id,
            model=model,
            title=title,
            prompt=prompt,
            output_path=output_path,
            model_check=model_check,
            packet_path=packet_path,
        )


if __name__ == "__main__":
    main()
