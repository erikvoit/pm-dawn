#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import (
    attach_instructions,
    check_active_harness_model,
    emit_json,
    ensure_pm_dawn_ignored,
    latest_session_by_title,
    launch_tmux_session_with_tail,
    opencode_server_session_name,
    opencode_slice_tmux_session_name,
    pi_attach_instructions,
    pi_runner_script,
    pi_session_dir,
    pi_slice_tmux_session_name,
    pi_tail_script,
    poll_for_session,
    require_cli,
    repo_root,
    run_cmd,
    slice_title,
    tmux_has_session,
)
from pm_dawn_core.implement import (
    build_launch_prompt,
    harness_monitoring_settings,
    implementation_review_monitor_state,
    load_execution_input,
    packet_plan_monitor_state,
    packet_plan_requires_acceptance,
    resolve_agent_harness,
    resolve_approved_plan_path,
    resolve_harness_model,
    resolve_packet_plan_review_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch a .pm-dawn implementation session through the configured harness.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime", choices=("server", "tmux-run"), default="server")
    parser.add_argument("--phase", choices=("planning", "implementing"), default="implementing")
    parser.add_argument("--approved-plan")
    parser.add_argument("--harness")
    parser.add_argument("--model")
    parser.add_argument("--server-url", default="http://127.0.0.1:4096")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def record_run(args: argparse.Namespace, handoff: dict, handoff_path: Path, payload: dict) -> None:
    cmd = [
        sys.executable,
        str(Path(__file__).with_name("record_slice_run.py")),
        args.epic_key,
        args.group_id,
        "--repo-root",
        args.repo_root,
        "--handoff-path",
        str(handoff_path),
        "--branch-name",
        handoff["branch_name"],
        "--runtime-mode",
        payload["runtime_mode"],
        "--harness",
        payload["harness"],
        "--model",
        payload["model"],
        "--status",
        payload["status"],
        "--phase",
        args.phase,
        "--completion-state",
        "in_progress",
        "--last-action",
        payload["last_action"],
    ]
    if payload.get("model_check") is not None:
        cmd += ["--model-check", json.dumps(payload["model_check"], sort_keys=True)]
    if payload.get("monitoring") is not None:
        cmd += ["--monitoring", json.dumps(payload["monitoring"], sort_keys=True)]
    if payload.get("server_url"):
        cmd += ["--server-url", payload["server_url"]]
    if payload.get("opencode_session_id"):
        cmd += ["--session-id", payload["opencode_session_id"]]
    if payload.get("tmux_session"):
        cmd += ["--tmux-session", payload["tmux_session"]]
    if payload.get("server_tmux_session"):
        cmd += ["--server-tmux-session", payload["server_tmux_session"]]
    if payload.get("session_dir"):
        cmd += ["--session-dir", payload["session_dir"]]
    if payload.get("approved_plan"):
        approved_plan = str(payload["approved_plan"])
        if approved_plan.endswith(".implementation-plan.md") or approved_plan.endswith(".opencode-plan.md"):
            cmd += ["--implementation-plan-artifact", approved_plan]
        else:
            cmd += ["--plan-artifact", approved_plan]
    if args.packet_id:
        cmd += ["--packet-id", args.packet_id]
    for item in payload.get("attach_instructions", []):
        cmd += ["--attach", item]
    run_cmd(cmd)


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    harness = resolve_agent_harness(
        root,
        explicit_harness=args.harness,
        phase=args.phase,
    )
    model = resolve_harness_model(
        root,
        harness=harness,
        explicit_model=args.model,
        phase=args.phase,
        packet_id=args.packet_id,
    )
    model_check = check_active_harness_model(harness, model)
    handoff, handoff_path = load_execution_input(root, args.epic_key, args.group_id, args.packet_id)
    ignore_state = ensure_pm_dawn_ignored(root)
    approved_plan = resolve_approved_plan_path(root, args.epic_key, args.packet_id, args.approved_plan)
    review_state = resolve_packet_plan_review_state(root, args.epic_key, args.packet_id) if args.packet_id else None
    plan_monitor = (
        packet_plan_monitor_state(root, args.epic_key, args.packet_id, state=review_state)
        if args.packet_id
        else None
    )
    if args.phase == "implementing" and args.packet_id:
        if args.approved_plan is None and packet_plan_requires_acceptance(root, args.epic_key, args.packet_id):
            if review_state is None:
                raise SystemExit(
                    "packet implementation is blocked: a plan proposal exists but no plan-review state is recorded yet"
                )
            if review_state.get("status") != "accepted":
                raise SystemExit(
                    "packet implementation is blocked until plan review is accepted; "
                    f"current status is {review_state.get('status')!r}"
                )
        if approved_plan is None and review_state is not None and review_state.get("status") == "accepted":
            raise SystemExit(
                "packet plan review is accepted but no reviewer-approved implementation plan artifact is available"
            )
    prompt = build_launch_prompt(handoff, handoff_path, root, phase=args.phase, approved_plan_path=approved_plan)
    title = slice_title(args.epic_key, args.group_id, args.phase, args.packet_id)

    payload = {
        "epic_key": args.epic_key,
        "group_id": args.group_id,
        "harness": harness,
        "runtime_mode": args.runtime,
        "model": model,
        "ignore_state": ignore_state,
        "branch_name": handoff["branch_name"],
        "handoff_path": str(handoff_path),
        "packet_id": args.packet_id,
        "model_check": model_check,
        "status": "prepared" if args.dry_run else "launched",
        "last_action": "prepare" if args.dry_run else "launch",
        "server_url": None,
        "opencode_session_id": None,
        "tmux_session": None,
        "server_tmux_session": None,
        "session_dir": None,
        "attach_instructions": [],
        "title": title,
        "plan_review": review_state if args.packet_id else None,
        "plan_monitor": plan_monitor,
    }
    if approved_plan:
        payload["approved_plan"] = str(approved_plan)
    payload["monitoring"] = harness_monitoring_settings(root, harness)
    payload["implementation_monitor"] = (
        implementation_review_monitor_state(
            root,
            args.epic_key,
            args.group_id,
            args.packet_id,
            status=payload["status"],
            completion_state="in_progress",
            worker=None,
            last_action=payload["last_action"],
        )
        if args.phase == "implementing"
        else None
    )

    if args.dry_run:
        if harness == "pi":
            payload["runtime_mode"] = "tmux-run"
            payload["attach_instructions"] = pi_attach_instructions(None)
        elif args.runtime == "server":
            payload["server_url"] = args.server_url
            payload["attach_instructions"] = attach_instructions(args.server_url, None, None, root)
        else:
            payload["attach_instructions"] = attach_instructions(None, None, None, root)
        emit_json(payload)
        return

    if harness == "opencode" and args.runtime == "server":
        require_cli("opencode")
        parsed = urlparse(args.server_url)
        server_session = opencode_server_session_name(root)
        if not tmux_has_session(server_session):
            ensure_cmd = [
                sys.executable,
                str(Path(__file__).with_name("ensure_opencode_server.py")),
                "--repo-root",
                str(root),
                "--port",
                str(parsed.port or 4096),
                "--hostname",
                parsed.hostname or "127.0.0.1",
            ]
            server_data = json.loads(run_cmd(ensure_cmd).stdout)
        else:
            server_data = {"server_url": args.server_url, "tmux_session": server_session, "status": "already_running"}
        payload["server_url"] = server_data["server_url"]
        payload["server_tmux_session"] = server_data["tmux_session"]

    if harness == "pi":
        require_cli("pi")
        worker_session = pi_slice_tmux_session_name(args.epic_key, args.group_id, args.packet_id)
        session_dir = pi_session_dir(root, args.epic_key, args.group_id, args.packet_id, args.phase)
        session_dir.mkdir(parents=True, exist_ok=True)
        cmd = (
            f"cd {shlex.quote(str(root))} && "
            f"pi --print --model {shlex.quote(model)} --session-dir {shlex.quote(str(session_dir))} "
            f"{shlex.quote(prompt)}"
        )
        launch_tmux_session_with_tail(
            session_name=worker_session,
            cwd=root,
            runner_script=pi_runner_script(root=root, session_dir=session_dir, command=cmd),
            tail_script=pi_tail_script(session_dir=session_dir),
        )
        payload["runtime_mode"] = "tmux-run"
        payload["tmux_session"] = worker_session
        payload["session_dir"] = str(session_dir)
        payload["attach_instructions"] = pi_attach_instructions(worker_session)
    elif args.runtime == "server":
        require_cli("opencode")
        worker_session = opencode_slice_tmux_session_name(args.epic_key, args.group_id, args.packet_id)
        cmd = (
            f"cd {shlex.quote(str(root))} && "
            f"opencode run --attach {shlex.quote(payload['server_url'])} --dir {shlex.quote(str(root))} "
            f"--model {shlex.quote(model)} --title {shlex.quote(title)} {shlex.quote(prompt)}"
        )
        run_cmd(["tmux", "new-session", "-d", "-s", worker_session, cmd])
        payload["tmux_session"] = worker_session
        session = poll_for_session(
            title,
            timeout_seconds=max(20, int(payload["monitoring"]["initial_session_check_seconds"])),
        )
        if session:
            payload["opencode_session_id"] = session.get("id")
        payload["attach_instructions"] = attach_instructions(payload["server_url"], payload["opencode_session_id"], worker_session, root)
    else:
        require_cli("opencode")
        worker_session = opencode_slice_tmux_session_name(args.epic_key, args.group_id, args.packet_id)
        cmd = (
            f"cd {shlex.quote(str(root))} && "
            f"opencode run --dir {shlex.quote(str(root))} "
            f"--model {shlex.quote(model)} --title {shlex.quote(title)} {shlex.quote(prompt)}"
        )
        run_cmd(["tmux", "new-session", "-d", "-s", worker_session, cmd])
        payload["tmux_session"] = worker_session
        session = latest_session_by_title(title)
        if session:
            payload["opencode_session_id"] = session.get("id")
        payload["attach_instructions"] = attach_instructions(None, None, worker_session, root)

    record_run(args, handoff, handoff_path, payload)
    emit_json(payload)


if __name__ == "__main__":
    main()
