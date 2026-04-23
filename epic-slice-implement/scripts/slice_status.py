#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import (
    emit_json,
    export_session_json,
    infer_phase,
    latest_completed_assistant_message,
    read_json,
    session_completion_state,
    session_runtime_status,
)
from pm_dawn_core.layout import run_metadata_path
from pm_dawn_core.implement import packet_plan_monitor_state, resolve_packet_plan_review_state
from pm_dawn_core.profile import repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report current status for a .pm-dawn slice run.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    path = run_metadata_path(root, args.epic_key, args.group_id)
    if not path.exists():
        raise SystemExit(f"run metadata not found: {path}")
    data = read_json(path)
    packet_id = data.get("packet_id")
    plan_review = (
        resolve_packet_plan_review_state(root, args.epic_key, packet_id)
        if isinstance(packet_id, str) and packet_id
        else None
    )
    plan_monitor = (
        packet_plan_monitor_state(root, args.epic_key, packet_id, state=plan_review)
        if isinstance(packet_id, str) and packet_id
        else None
    )
    harness = data.get("harness", "opencode")
    runtime = data.get("runtime", {})
    tmux_session = runtime.get("tmux_session") or data.get("opencode", {}).get("tmux_session")
    server_tmux_session = runtime.get("server_tmux_session") or data.get("opencode", {}).get("server_tmux_session")
    session_id = runtime.get("session_id") or data.get("opencode", {}).get("session_id")
    phase = data.get("phase")
    completion_state = data.get("completion_state")
    last_completed_at = None

    if harness == "opencode" and session_id:
        try:
            session_export = export_session_json(session_id)
        except RuntimeError:
            session_export = None
        if session_export:
            phase = infer_phase(data, session_export)
            completion_state = session_completion_state(session_export)
            status = session_runtime_status(data, completion_state)
            completed_message = latest_completed_assistant_message(session_export)
            if completed_message:
                last_completed_at = completed_message.get("info", {}).get("time", {}).get("completed")
        else:
            status = data.get("status", "stopped")
    else:
        status = data.get("status", "stopped")

    payload = {
        "harness": harness,
        "status": status,
        "phase": phase,
        "completion_state": completion_state,
        "runtime_mode": data.get("runtime_mode"),
        "model": data.get("model"),
        "model_check": data.get("model_check"),
        "server_url": runtime.get("server_url") or data.get("opencode", {}).get("server_url"),
        "tmux_session": tmux_session,
        "server_tmux_session": server_tmux_session,
        "session_id": session_id,
        "session_dir": runtime.get("session_dir"),
        "attach_instructions": data.get("attach_instructions", []),
        "branch_name": data.get("branch_name"),
        "packet_id": data.get("packet_id"),
        "plan_review": plan_review,
        "plan_monitor": plan_monitor,
        "handoff_path": data.get("handoff_path"),
        "last_action": data.get("last_action"),
        "artifacts": data.get("artifacts", {}),
        "worker": data.get("worker", {}),
        "last_completed_at": last_completed_at,
    }
    emit_json(payload)


if __name__ == "__main__":
    main()
