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
    now_iso,
    repo_root,
    write_json,
)
from harness_opencode import run_packet_planning as run_opencode_packet_planning
from harness_pi import run_packet_planning as run_pi_packet_planning
from pm_dawn_core.implement import (
    initialize_packet_plan_review_state,
    packet_markdown_path,
    packet_plan_monitor_state,
    render_implement_command,
    resolve_agent_harness,
    resolve_harness_model,
    resolve_implement_command,
    resolve_packet_plan_review_state,
)
from pm_dawn_core.layout import packet_plan_artifacts


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
    artifacts = packet_plan_artifacts(root, args.epic_key, args.packet_id)
    review_state = resolve_packet_plan_review_state(root, args.epic_key, args.packet_id)
    monitor_state = packet_plan_monitor_state(
        root,
        args.epic_key,
        args.packet_id,
        state=review_state,
    )
    if monitor_state["accepted"]:
        raise SystemExit("packet plan review is already accepted; no new planning run is required")
    if review_state is not None and review_state.get("status") == "response_submitted":
        raise SystemExit(
            "packet plan response is already submitted; wait for reviewer action before re-running planning"
        )
    if review_state is not None and review_state.get("status") == "rejected":
        raise SystemExit(
            "packet plan review is rejected; clear or replace the review state before re-running planning"
        )

    revision_mode = bool(monitor_state["requires_revision_run"])
    output_path = artifacts.response_md if revision_mode else artifacts.proposal_md

    if not packet_path.exists():
        raise SystemExit(f"packet Markdown not found: {packet_path}")

    title = args.title or f"packet-plan:{args.epic_key}:{args.packet_id}"
    proposal_review_command = render_implement_command(
        root,
        "review-plan",
        args.epic_key,
        args.group_id,
        args.packet_id,
        "--action",
        "accept",
        "--repo-root",
        ".",
    )
    if revision_mode:
        review_artifact = artifacts.review_md
        if not review_artifact.exists():
            raise SystemExit(
                "packet plan revision is requested but no plan review artifact exists for the current packet"
            )
        prompt = (
            "Use the packet-implementation-plan skill. "
            f"Read {packet_path}. "
            f"Read the current review feedback at {review_artifact}. "
            f"Produce the revised implementation plan response only and write it to {output_path}. "
            "Do not edit code, do not switch branches, and do not implement the packet. "
            "This run is not successful unless the response file exists at the required path when you finish. "
            "Treat the written artifact as a worker-authored response for reviewer negotiation, not as a self-approved brief. "
            f"The canonical PM Dawn acceptance command for this action is: {proposal_review_command}"
        )
    else:
        prompt = (
            "Use the packet-implementation-plan skill. "
            f"Read {packet_path} and produce the implementation plan proposal only. "
            f"Write it to {output_path}. "
            "Do not edit code, do not switch branches, and do not implement the packet. "
            "This run is not successful unless the plan file exists at the required path when you finish. "
            "Treat the written artifact as a worker-authored proposal for reviewer negotiation, not as a self-approved brief. "
            f"The canonical PM Dawn acceptance command for this action is: {proposal_review_command}"
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
    if output_path.exists():
        if revision_mode:
            state_path = artifacts.review_state_json
            updated_state = dict(review_state or {})
            updated_state.update(
                {
                    "schema_version": "v1",
                    "epic_key": args.epic_key,
                    "group_id": args.group_id,
                    "packet_id": args.packet_id,
                    "status": "response_submitted",
                    "response_artifact": str(output_path.resolve()),
                    "current_artifact": str(output_path.resolve()),
                    "submitted_artifact": str(output_path.resolve()),
                    "accepted_artifact": None,
                    "accepted_at": None,
                    "last_action": "response_submitted",
                    "updated": now_iso(),
                }
            )
            write_json(state_path, updated_state)
        else:
            initialize_packet_plan_review_state(root, args.epic_key, args.packet_id)


if __name__ == "__main__":
    main()
