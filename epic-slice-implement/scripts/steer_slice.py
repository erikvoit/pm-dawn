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
    attach_instructions,
    build_steer_prompt,
    emit_json,
    read_json,
)
from harness_pi_embedded import PiEmbeddedSessionAdapter
from pm_dawn_core.layout import run_metadata_path
from pm_dawn_core.implement import implementation_review_monitor_state
from pm_dawn_core.markdown import parse_slice_markdown
from pm_dawn_core.profile import repo_root
from pm_dawn_core.runtime import require_cli, run_cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a steering message to an existing .pm-dawn slice session.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("steering_message")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    run_path = run_metadata_path(root, args.epic_key, args.group_id)
    if not run_path.exists():
        raise SystemExit(f"run metadata not found: {run_path}")
    run_meta = read_json(run_path)
    harness = run_meta.get("harness", "opencode")
    handoff_path = Path(run_meta["handoff_path"])
    if handoff_path.suffix == ".json":
        handoff = read_json(handoff_path)
    else:
        handoff = parse_slice_markdown(handoff_path)
    runtime = run_meta.get("runtime_mode")
    implementation_monitor = (
        implementation_review_monitor_state(
            root,
            args.epic_key,
            args.group_id,
            run_meta.get("packet_id"),
            status=run_meta.get("status"),
            completion_state=run_meta.get("completion_state"),
            worker=run_meta.get("worker", {}),
            last_action=run_meta.get("last_action"),
        )
        if run_meta.get("phase", "implementing") == "implementing"
        else None
    )
    if implementation_monitor is not None and implementation_monitor["review_ready"]:
        emit_json(
            {
                "status": "review_boundary_reached",
                "reason": "worker is already pending review; review or accept the packet before sending more steering",
                "implementation_monitor": implementation_monitor,
                "attach_instructions": run_meta.get("attach_instructions", []),
            }
        )
        return
    prompt = build_steer_prompt(handoff, handoff_path, root, args.steering_message)

    if harness == "pi" and (runtime == "embedded" or run_meta.get("embedded_session")):
        embedded_snapshot = PiEmbeddedSessionAdapter(root=root).steer(args.steering_message)
        payload = {
            "status": "manual_followup_required",
            "reason": (
                "embedded Pi steering is unavailable; use the existing artifact-driven revision "
                "relaunch flow or continue in the Pi tmux session"
            ),
            "embedded_session": embedded_snapshot.to_payload(),
            "attach_instructions": run_meta.get("attach_instructions", []),
        }
        emit_json(payload)
        return

    if harness != "opencode" or runtime == "tmux-run":
        payload = {
            "status": "manual_followup_required",
            "reason": "active steering is only supported for server-backed opencode sessions; for pi or tmux-run sessions, continue in tmux or relaunch with updated guidance",
            "attach_instructions": run_meta.get("attach_instructions", []),
        }
        emit_json(payload)
        return

    runtime_meta = run_meta.get("runtime", {})
    server_url = runtime_meta.get("server_url") or run_meta.get("opencode", {}).get("server_url")
    session_id = runtime_meta.get("session_id") or run_meta.get("opencode", {}).get("session_id")
    if not server_url or not session_id:
        raise SystemExit("server mode steering requires both server_url and session_id in run metadata")

    require_cli("opencode")
    cmd = [
        "opencode",
        "run",
        "--attach",
        server_url,
        "--dir",
        str(root),
        "--session",
        session_id,
        "--model",
        run_meta.get("model", "llama/qwen/qwen3-coder-next"),
        prompt,
    ]
    run_cmd(cmd)
    record_cmd = [
        sys.executable,
        str(Path(__file__).with_name("record_slice_run.py")),
        args.epic_key,
        args.group_id,
        "--repo-root",
        str(root),
        "--handoff-path",
        run_meta["handoff_path"],
        "--branch-name",
        run_meta["branch_name"],
        "--runtime-mode",
        runtime,
        "--harness",
        harness,
        "--model",
        run_meta["model"],
        "--status",
        "steered",
        "--phase",
        run_meta.get("phase", "implementing"),
        "--completion-state",
        "in_progress",
        "--server-url",
        server_url,
        "--session-id",
        session_id,
        "--last-action",
        "steer",
    ]
    if run_meta.get("model_check") is not None:
        record_cmd += ["--model-check", json.dumps(run_meta["model_check"], sort_keys=True)]
    tmux_session = runtime_meta.get("tmux_session") or run_meta.get("opencode", {}).get("tmux_session")
    server_tmux = runtime_meta.get("server_tmux_session") or run_meta.get("opencode", {}).get("server_tmux_session")
    if tmux_session:
        record_cmd += ["--tmux-session", tmux_session]
    if server_tmux:
        record_cmd += ["--server-tmux-session", server_tmux]
    for item in run_meta.get("attach_instructions", []):
        record_cmd += ["--attach", item]
    run_cmd(record_cmd)

    emit_json(
        {
            "status": "steered",
            "server_url": server_url,
            "opencode_session_id": session_id,
            "attach_instructions": attach_instructions(server_url, session_id, tmux_session, root),
        }
    )


if __name__ == "__main__":
    main()
