#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    emit_json,
    export_session_json,
    infer_phase,
    latest_completed_assistant_message,
    now_iso,
    read_json,
    render_phase_artifact,
    repo_root,
    run_artifact_path,
    run_metadata_path,
    session_completion_state,
    session_runtime_status,
    write_json,
    write_text,
)


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
    harness = run_meta.get("harness", "opencode")
    runtime = run_meta.get("runtime", {})
    session_id = runtime.get("session_id") or run_meta.get("opencode", {}).get("session_id")
    if harness != "opencode":
        payload = {
            "status": run_meta.get("status", "unknown"),
            "phase": run_meta.get("phase"),
            "completion_state": run_meta.get("completion_state"),
            "harness": harness,
            "session_dir": runtime.get("session_dir"),
            "artifacts": run_meta.get("artifacts", {}),
            "worker": run_meta.get("worker", {}),
            "warning": "transcript sync is currently only supported for opencode-backed sessions",
        }
        emit_json(payload)
        return
    if not session_id:
        raise SystemExit("run metadata does not include an opencode session id")

    try:
        session_export = export_session_json(session_id)
    except RuntimeError as exc:
        payload = {
            "status": run_meta.get("status", "unknown"),
            "phase": run_meta.get("phase"),
            "completion_state": run_meta.get("completion_state"),
            "opencode_session_id": session_id,
            "artifacts": run_meta.get("artifacts", {}),
            "worker": run_meta.get("worker", {}),
            "warning": str(exc),
        }
        emit_json(payload)
        return
    phase = args.phase or infer_phase(run_meta, session_export)
    completion_state = session_completion_state(session_export)
    status = session_runtime_status(run_meta, completion_state)
    completed_message = latest_completed_assistant_message(session_export, require_text=True)

    artifacts = run_meta.get("artifacts", {}).copy() if isinstance(run_meta.get("artifacts"), dict) else {}
    should_write = False
    if args.write_artifacts and completed_message:
        if phase == "planning":
            should_write = True
        elif completion_state == "completed":
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
    }
    emit_json(payload)


if __name__ == "__main__":
    main()
