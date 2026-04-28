from __future__ import annotations

import json
from pathlib import Path

from .artifacts import read_json
from .implement import (
    implementation_review_monitor_state,
    packet_plan_monitor_state,
    resolve_packet_plan_review_state,
)
from .layout import run_metadata_path


def load_run_metadata(root: Path, epic_key: str, group_id: str) -> tuple[dict, Path]:
    path = run_metadata_path(root, epic_key, group_id)
    if not path.exists():
        raise RuntimeError(f"run metadata not found: {path}")
    return read_json(path), path


def decode_json_arg(value: str | None, existing: object = None) -> object:
    if value:
        return json.loads(value)
    return existing


def run_plan_review_state(root: Path, epic_key: str, packet_id: object) -> dict | None:
    if isinstance(packet_id, str) and packet_id:
        return resolve_packet_plan_review_state(root, epic_key, packet_id)
    return None


def run_plan_monitor_state(
    root: Path,
    epic_key: str,
    packet_id: object,
    *,
    plan_review: dict | None = None,
) -> dict | None:
    if isinstance(packet_id, str) and packet_id:
        return packet_plan_monitor_state(root, epic_key, packet_id, state=plan_review)
    return None


def run_implementation_monitor_state(
    root: Path,
    epic_key: str,
    group_id: str,
    run_meta: dict,
    *,
    phase: str | None = None,
    status: str | None = None,
    completion_state: str | None = None,
) -> dict | None:
    resolved_phase = phase if phase is not None else run_meta.get("phase")
    if resolved_phase != "implementing":
        return None
    packet_id = run_meta.get("packet_id")
    return implementation_review_monitor_state(
        root,
        epic_key,
        group_id,
        packet_id if isinstance(packet_id, str) else None,
        status=status,
        completion_state=completion_state,
        worker=run_meta.get("worker", {}),
        last_action=run_meta.get("last_action"),
    )


def apply_implementation_monitor_status(
    root: Path,
    epic_key: str,
    group_id: str,
    run_meta: dict,
    *,
    phase: str | None,
    status: str | None,
    completion_state: str | None,
) -> tuple[str | None, str | None, dict | None]:
    monitor = run_implementation_monitor_state(
        root,
        epic_key,
        group_id,
        run_meta,
        phase=phase,
        status=status,
        completion_state=completion_state,
    )
    if monitor is None:
        return status, completion_state, None
    return monitor["status"], monitor["completion_state"], monitor


def merge_run_metadata(
    *,
    existing: dict,
    epic_key: str,
    group_id: str,
    handoff_path: str,
    packet_id: str | None,
    branch_name: str,
    runtime_mode: str,
    harness: str,
    model: str,
    status: str,
    phase: str | None,
    completion_state: str | None,
    server_url: str | None,
    session_id: str | None,
    tmux_session: str | None,
    server_tmux_session: str | None,
    session_dir: str | None,
    last_action: str,
    attach_instructions: list[str],
    plan_artifact: str | None,
    implementation_plan_artifact: str | None,
    result_artifact: str | None,
    worker_status: str | None,
    worker_note: str | None,
    model_check: object,
    monitoring: object,
    embedded_session: object,
    created_at: str,
    updated_at: str,
) -> dict:
    artifacts = existing.get("artifacts", {}).copy() if isinstance(existing.get("artifacts"), dict) else {}
    if plan_artifact:
        artifacts["plan_md"] = str(Path(plan_artifact).resolve())
    if implementation_plan_artifact:
        artifacts["implementation_plan_md"] = str(Path(implementation_plan_artifact).resolve())
    if result_artifact:
        artifacts["result_md"] = str(Path(result_artifact).resolve())

    worker = existing.get("worker", {}).copy() if isinstance(existing.get("worker"), dict) else {}
    if worker_status:
        worker["status"] = worker_status
        worker["updated"] = updated_at
    if worker_note:
        worker["note"] = worker_note
        worker.setdefault("updated", updated_at)

    payload = {
        "schema_version": "v1",
        "epic_key": epic_key,
        "group_id": group_id,
        "handoff_path": str(Path(handoff_path).resolve()),
        "packet_id": packet_id,
        "branch_name": branch_name,
        "harness": harness,
        "runtime_mode": runtime_mode,
        "model": model,
        "model_check": model_check,
        "status": status,
        "phase": phase,
        "completion_state": completion_state,
        "runtime": {
            "server_url": server_url,
            "session_id": session_id,
            "tmux_session": tmux_session,
            "server_tmux_session": server_tmux_session,
            "session_dir": session_dir,
        },
        "time": {
            "created": created_at,
            "updated": updated_at,
        },
        "last_action": last_action,
        "attach_instructions": attach_instructions,
        "artifacts": artifacts,
        "worker": worker,
        "monitoring": monitoring,
        "embedded_session": embedded_session,
    }
    if harness == "opencode":
        payload["opencode"] = {
            "server_url": server_url,
            "session_id": session_id,
            "tmux_session": tmux_session,
            "server_tmux_session": server_tmux_session,
        }
    return payload
