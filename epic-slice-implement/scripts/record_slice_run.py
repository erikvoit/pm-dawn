#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import emit_json, now_iso, read_json, write_json
from pm_dawn_core.layout import run_metadata_path
from pm_dawn_core.profile import repo_root
from pm_dawn_core.runs import decode_json_arg, merge_run_metadata


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
    parser.add_argument("--embedded-session")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    path = run_metadata_path(root, args.epic_key, args.group_id)
    existing = read_json(path) if path.exists() else {}
    created = existing.get("time", {}).get("created", now_iso())
    phase = args.phase or existing.get("phase")
    completion_state = args.completion_state or existing.get("completion_state")
    updated = now_iso()
    payload = merge_run_metadata(
        existing=existing,
        epic_key=args.epic_key,
        group_id=args.group_id,
        handoff_path=args.handoff_path,
        packet_id=args.packet_id,
        branch_name=args.branch_name,
        runtime_mode=args.runtime_mode,
        harness=args.harness,
        model=args.model,
        status=args.status,
        phase=phase,
        completion_state=completion_state,
        server_url=args.server_url,
        session_id=args.session_id,
        tmux_session=args.tmux_session,
        server_tmux_session=args.server_tmux_session,
        session_dir=args.session_dir,
        last_action=args.last_action,
        attach_instructions=args.attach,
        plan_artifact=args.plan_artifact,
        implementation_plan_artifact=args.implementation_plan_artifact,
        result_artifact=args.result_artifact,
        worker_status=args.worker_status,
        worker_note=args.worker_note,
        model_check=decode_json_arg(args.model_check, existing.get("model_check")),
        monitoring=decode_json_arg(args.monitoring, existing.get("monitoring")),
        embedded_session=decode_json_arg(args.embedded_session, existing.get("embedded_session")),
        created_at=created,
        updated_at=updated,
    )
    write_json(path, payload)
    emit_json(payload)


if __name__ == "__main__":
    main()
