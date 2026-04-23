#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import emit_json, now_iso, read_json, write_json
from pm_dawn_core.layout import run_metadata_path
from pm_dawn_core.profile import repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write or update .pm-dawn slice run metadata.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--handoff-path", required=True)
    parser.add_argument("--packet-id")
    parser.add_argument("--branch-name", required=True)
    parser.add_argument("--runtime-mode", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--phase")
    parser.add_argument("--completion-state")
    parser.add_argument("--server-url")
    parser.add_argument("--session-id")
    parser.add_argument("--tmux-session")
    parser.add_argument("--server-tmux-session")
    parser.add_argument("--session-dir")
    parser.add_argument("--last-action", required=True)
    parser.add_argument("--attach", action="append", default=[])
    parser.add_argument("--plan-artifact")
    parser.add_argument("--implementation-plan-artifact")
    parser.add_argument("--result-artifact")
    parser.add_argument("--worker-status")
    parser.add_argument("--worker-note")
    parser.add_argument("--model-check")
    parser.add_argument("--monitoring")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    path = run_metadata_path(root, args.epic_key, args.group_id)
    existing = read_json(path) if path.exists() else {}
    created = existing.get("time", {}).get("created", now_iso())
    phase = args.phase or existing.get("phase")
    completion_state = args.completion_state or existing.get("completion_state")
    artifacts = existing.get("artifacts", {}).copy() if isinstance(existing.get("artifacts"), dict) else {}
    if args.plan_artifact:
        artifacts["plan_md"] = str(Path(args.plan_artifact).resolve())
    if args.implementation_plan_artifact:
        artifacts["implementation_plan_md"] = str(Path(args.implementation_plan_artifact).resolve())
    if args.result_artifact:
        artifacts["result_md"] = str(Path(args.result_artifact).resolve())
    worker = existing.get("worker", {}).copy() if isinstance(existing.get("worker"), dict) else {}
    if args.worker_status:
        worker["status"] = args.worker_status
        worker["updated"] = now_iso()
    if args.worker_note:
        worker["note"] = args.worker_note
        worker.setdefault("updated", now_iso())
    model_check = existing.get("model_check")
    if args.model_check:
        model_check = json.loads(args.model_check)
    monitoring = existing.get("monitoring")
    if args.monitoring:
        monitoring = json.loads(args.monitoring)
    payload = {
        "schema_version": "v1",
        "epic_key": args.epic_key,
        "group_id": args.group_id,
        "handoff_path": str(Path(args.handoff_path).resolve()),
        "packet_id": args.packet_id,
        "branch_name": args.branch_name,
        "harness": args.harness,
        "runtime_mode": args.runtime_mode,
        "model": args.model,
        "model_check": model_check,
        "status": args.status,
        "phase": phase,
        "completion_state": completion_state,
        "runtime": {
            "server_url": args.server_url,
            "session_id": args.session_id,
            "tmux_session": args.tmux_session,
            "server_tmux_session": args.server_tmux_session,
            "session_dir": args.session_dir,
        },
        "time": {
            "created": created,
            "updated": now_iso(),
        },
        "last_action": args.last_action,
        "attach_instructions": args.attach,
        "artifacts": artifacts,
        "worker": worker,
        "monitoring": monitoring,
    }
    if args.harness == "opencode":
        payload["opencode"] = {
            "server_url": args.server_url,
            "session_id": args.session_id,
            "tmux_session": args.tmux_session,
            "server_tmux_session": args.server_tmux_session,
        }
    write_json(path, payload)
    emit_json(payload)


if __name__ == "__main__":
    main()
