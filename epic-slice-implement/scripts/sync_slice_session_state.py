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
    now_iso,
    read_json,
    render_phase_artifact,
    session_completion_state,
    session_runtime_status,
    write_json,
    write_text,
)
from pm_dawn_core.layout import run_artifact_path, run_metadata_path
from pm_dawn_core.implement import (
    implementation_review_monitor_state,
    packet_plan_monitor_state,
    resolve_packet_plan_review_state,
)
from pm_dawn_core.profile import repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync .pm-dawn run metadata from the actual opencode session state.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--phase", choices=("planning", "implementing"))
    parser.add_argument("--write-artifacts", action="store_true")
    parser.add_argument("--overwrite-artifacts", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    path = run_metadata_path(root, args.epic_key, args.group_id)
    if not path.exists():
        raise SystemExit(f"run metadata not found: {path}")

    run_meta = read_json(path)
    packet_id = run_meta.get("packet_id")
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

    def resolve_implementation_monitor(
        *,
        phase: str | None,
        status: str | None,
        completion_state: str | None,
    ) -> dict | None:
        if phase != "implementing":
            return None
        return implementation_review_monitor_state(
            root,
            args.epic_key,
            args.group_id,
            packet_id if isinstance(packet_id, str) else None,
            status=status,
            completion_state=completion_state,
            worker=run_meta.get("worker", {}),
            last_action=run_meta.get("last_action"),
        )

    def resolved_status_payload(
        *,
        phase: str | None,
        status: str | None,
        completion_state: str | None,
    ) -> tuple[str | None, str | None, dict | None]:
        implementation_monitor = resolve_implementation_monitor(
            phase=phase,
            status=status,
            completion_state=completion_state,
        )
        if implementation_monitor is None:
            return status, completion_state, None
        return (
            implementation_monitor["status"],
            implementation_monitor["completion_state"],
            implementation_monitor,
        )

    harness = run_meta.get("harness", "opencode")
    runtime = run_meta.get("runtime", {})
    session_id = runtime.get("session_id") or run_meta.get("opencode", {}).get("session_id")
    if harness != "opencode":
        status, completion_state, implementation_monitor = resolved_status_payload(
            phase=run_meta.get("phase"),
            status=run_meta.get("status"),
            completion_state=run_meta.get("completion_state"),
        )
        payload = {
            "status": status or run_meta.get("status", "unknown"),
            "phase": run_meta.get("phase"),
            "completion_state": completion_state,
            "harness": harness,
            "session_dir": runtime.get("session_dir"),
            "artifacts": run_meta.get("artifacts", {}),
            "worker": run_meta.get("worker", {}),
            "plan_review": plan_review,
            "plan_monitor": plan_monitor,
            "implementation_monitor": implementation_monitor,
            "warning": "transcript sync is currently only supported for opencode-backed sessions",
        }
        emit_json(payload)
        return
    if not session_id:
        raise SystemExit("run metadata does not include an opencode session id")

    try:
        session_export = export_session_json(session_id)
    except RuntimeError as exc:
        status, completion_state, implementation_monitor = resolved_status_payload(
            phase=run_meta.get("phase"),
            status=run_meta.get("status"),
            completion_state=run_meta.get("completion_state"),
        )
        payload = {
            "status": status or run_meta.get("status", "unknown"),
            "phase": run_meta.get("phase"),
            "completion_state": completion_state,
            "opencode_session_id": session_id,
            "artifacts": run_meta.get("artifacts", {}),
            "worker": run_meta.get("worker", {}),
            "plan_review": plan_review,
            "plan_monitor": plan_monitor,
            "implementation_monitor": implementation_monitor,
            "warning": str(exc),
        }
        emit_json(payload)
        return
    phase = args.phase or infer_phase(run_meta, session_export)
    completion_state = session_completion_state(session_export)
    status = session_runtime_status(run_meta, completion_state)
    completed_message = latest_completed_assistant_message(session_export, require_text=True)
    status, completion_state, implementation_monitor = resolved_status_payload(
        phase=phase,
        status=status,
        completion_state=completion_state,
    )

    artifacts = run_meta.get("artifacts", {}).copy() if isinstance(run_meta.get("artifacts"), dict) else {}
    should_write = False
    if args.write_artifacts and completed_message:
        if phase == "planning":
            should_write = True
        elif completion_state == "completed":
            should_write = True
        elif implementation_monitor is not None and implementation_monitor["review_ready"]:
            should_write = True
    if should_write:
        artifact_kind = "plan" if phase == "planning" else "result"
        artifact_path = run_artifact_path(root, args.epic_key, args.group_id, artifact_kind)
        if args.overwrite_artifacts or not artifact_path.exists():
            content = render_phase_artifact(
                epic_key=args.epic_key,
                group_id=args.group_id,
                phase=phase,
                session_export=session_export,
                source_message=completed_message,
            )
            write_text(artifact_path, content)
        artifacts[f"{artifact_kind}_md"] = str(artifact_path.resolve())

    updated = {
        **run_meta,
        "status": status,
        "phase": phase,
        "completion_state": completion_state,
        "artifacts": artifacts,
        "worker": run_meta.get("worker", {}),
        "time": {
            "created": run_meta.get("time", {}).get("created", now_iso()),
            "updated": now_iso(),
        },
    }
    write_json(path, updated)

    payload = {
        "harness": harness,
        "status": status,
        "phase": phase,
        "completion_state": completion_state,
        "opencode_session_id": session_id,
        "session_title": session_export.get("info", {}).get("title"),
        "artifacts": artifacts,
        "worker": updated.get("worker", {}),
        "plan_review": plan_review,
        "plan_monitor": plan_monitor,
        "implementation_monitor": implementation_monitor,
    }
    emit_json(payload)


if __name__ == "__main__":
    main()
