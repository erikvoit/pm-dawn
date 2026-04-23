#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import emit_json, now_iso, write_json
from pm_dawn_core.implement import (
    packet_plan_monitor_state,
    packet_plan_review_state_template,
    resolve_implement_command,
    resolve_packet_plan_review_state,
)
from pm_dawn_core.layout import (
    packet_plan_artifacts,
    packet_plan_review_state_path,
)
from pm_dawn_core.profile import repo_root


def parse_args() -> argparse.Namespace:
    surface = resolve_implement_command("review-plan")
    parser = argparse.ArgumentParser(description=surface.description)
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("packet_id")
    parser.add_argument(
        "--action",
        required=True,
        choices=("submit-review", "submit-response", "accept", "reject"),
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--artifact")
    parser.add_argument("--note", default="")
    return parser.parse_args()


def load_state(root: Path, epic_key: str, packet_id: str) -> tuple[dict, Path]:
    artifacts = packet_plan_artifacts(root, epic_key, packet_id)
    state_path = artifacts.review_state_json
    existing = resolve_packet_plan_review_state(root, epic_key, packet_id)
    if existing is not None:
        return existing, state_path
    return (
        packet_plan_review_state_template(
            root,
            epic_key,
            packet_id,
            status="proposal_submitted",
            proposal_path=artifacts.proposal_md,
        ),
        state_path,
    )


def require_artifact(path: Path, label: str) -> Path:
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")
    return path.resolve()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    state, state_path = load_state(root, args.epic_key, args.packet_id)
    artifacts = packet_plan_artifacts(root, args.epic_key, args.packet_id)
    proposal_path = artifacts.proposal_md
    review_path = artifacts.review_md
    response_path = artifacts.response_md
    implementation_path = artifacts.implementation_plan_md
    current_time = now_iso()

    if args.action == "submit-review":
        artifact = (
            require_artifact(Path(args.artifact), "plan review artifact")
            if args.artifact
            else require_artifact(review_path, "plan review artifact")
        )
        state["status"] = "changes_requested"
        state["review_artifact"] = str(artifact)
        state["current_artifact"] = str(artifact)
        state["accepted_artifact"] = None
        state["accepted_at"] = None
        state["last_action"] = "review_submitted"
    elif args.action == "submit-response":
        artifact = (
            require_artifact(Path(args.artifact), "plan response artifact")
            if args.artifact
            else require_artifact(response_path, "plan response artifact")
        )
        state["status"] = "response_submitted"
        state["response_artifact"] = str(artifact)
        state["current_artifact"] = str(artifact)
        state["submitted_artifact"] = str(artifact)
        state["accepted_artifact"] = None
        state["accepted_at"] = None
        state["last_action"] = "response_submitted"
    elif args.action == "accept":
        if args.artifact:
            source = require_artifact(Path(args.artifact).resolve(), "accepted plan source artifact")
        elif response_path.exists():
            source = response_path.resolve()
        else:
            source = require_artifact(proposal_path, "plan proposal artifact")
        implementation_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, implementation_path)
        state["status"] = "accepted"
        state["current_artifact"] = str(source)
        state["submitted_artifact"] = str(source)
        state["implementation_plan_artifact"] = str(implementation_path.resolve())
        state["accepted_artifact"] = str(source)
        state["accepted_at"] = current_time
        state["last_action"] = "accepted"
    else:
        state["status"] = "rejected"
        state["accepted_artifact"] = None
        state["accepted_at"] = None
        state["last_action"] = "rejected"

    state["schema_version"] = "v1"
    state["epic_key"] = args.epic_key
    state["group_id"] = args.group_id
    state["packet_id"] = args.packet_id
    state.setdefault("proposal_artifact", str(proposal_path.resolve()))
    state.setdefault("review_artifact", str(review_path.resolve()) if review_path.exists() else None)
    state.setdefault("response_artifact", str(response_path.resolve()) if response_path.exists() else None)
    state["updated"] = current_time
    if args.note:
        state["note"] = args.note

    write_json(state_path, state)
    emit_json(
        {
            "status": state["status"],
            "state_path": str(state_path.resolve()),
            "proposal_artifact": str(proposal_path.resolve()),
            "review_artifact": state.get("review_artifact"),
            "response_artifact": state.get("response_artifact"),
            "implementation_plan_artifact": state.get("implementation_plan_artifact"),
            "accepted_artifact": state.get("accepted_artifact"),
            "last_action": state.get("last_action"),
            "plan_monitor": packet_plan_monitor_state(
                root,
                args.epic_key,
                args.packet_id,
                state=state,
            ),
        }
    )


if __name__ == "__main__":
    main()
