#!/usr/bin/env python3
from __future__ import annotations

import json
import shlex
import time
from pathlib import Path

from common import (
    emit_json,
    launch_tmux_session_with_tail,
    pi_runner_script,
    pi_tail_script,
    run_cmd,
    tmux_has_session,
    write_text,
)


def pi_plan_tmux_session_name(epic_key: str, packet_id: str) -> str:
    safe_epic = epic_key.replace("/", "-")
    safe_packet = packet_id.replace("/", "-")
    return f"pi-plan-{safe_epic}-{safe_packet}"


def pi_plan_attach_instructions(tmux_session: str, session_dir: Path) -> list[str]:
    return [
        f"tmux attach -t {tmux_session}",
        f"tmux list-panes -t {tmux_session} -F '#{{pane_index}} #{{pane_current_command}}'",
        f"tmux select-pane -t {tmux_session}:0.1",
        f"ls -la {session_dir}",
    ]


def latest_pi_session_log(session_dir: Path) -> Path | None:
    files = sorted(session_dir.glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def _assistant_text_from_entry(entry: dict) -> str:
    message = entry.get("message", {})
    if message.get("role") != "assistant":
        return ""
    parts = message.get("content", [])
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text":
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
    return "".join(texts).strip()


def salvage_plan_from_pi_session_log(session_dir: Path, epic_key: str, packet_id: str) -> str | None:
    log_path = latest_pi_session_log(session_dir)
    if log_path is None:
        return None
    headers = [
        f"# {epic_key} / {packet_id} / Implementation Plan",
        f"# {epic_key} / {packet_id} / OpenCode Implementation Plan",
    ]
    latest_text = ""
    for raw_line in log_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        text = _assistant_text_from_entry(entry)
        if text:
            latest_text = text
    for expected_header in headers:
        if expected_header in latest_text:
            return latest_text[latest_text.index(expected_header) :].rstrip() + "\n"
    return None


def run_packet_planning(
    *,
    root: Path,
    epic_key: str,
    packet_id: str,
    model: str,
    prompt: str,
    output_path: Path,
    model_check: dict,
    packet_path: Path,
    session_dir: Path,
    timeout_seconds: int = 300,
) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    tmux_session = pi_plan_tmux_session_name(epic_key, packet_id)
    if tmux_has_session(tmux_session):
        run_cmd(["tmux", "kill-session", "-t", tmux_session], check=False)
    cmd = (
        f"cd {shlex.quote(str(root))} && "
        f"pi --print --model {shlex.quote(model)} --session-dir {shlex.quote(str(session_dir))} "
        f"{shlex.quote(prompt)}"
    )
    launch_tmux_session_with_tail(
        session_name=tmux_session,
        cwd=root,
        runner_script=pi_runner_script(root=root, session_dir=session_dir, command=cmd),
        tail_script=pi_tail_script(session_dir=session_dir),
    )
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if output_path.exists():
            emit_json(
                {
                    "status": "completed",
                    "harness": "pi",
                    "model": model,
                    "model_check": model_check,
                    "packet_path": str(packet_path),
                    "output_path": str(output_path),
                    "tmux_session": tmux_session,
                    "session_dir": str(session_dir),
                    "attach_instructions": pi_plan_attach_instructions(tmux_session, session_dir),
                }
            )
            return
        if not tmux_has_session(tmux_session):
            break
        time.sleep(2)

    if output_path.exists():
        emit_json(
            {
                "status": "completed",
                "harness": "pi",
                "model": model,
                "model_check": model_check,
                "packet_path": str(packet_path),
                "output_path": str(output_path),
                "tmux_session": tmux_session,
                "session_dir": str(session_dir),
                "attach_instructions": pi_plan_attach_instructions(tmux_session, session_dir),
            }
        )
        return

    salvaged = salvage_plan_from_pi_session_log(session_dir, epic_key, packet_id)
    if salvaged is not None:
        write_text(output_path, salvaged)
        emit_json(
            {
                "status": "completed",
                "harness": "pi",
                "model": model,
                "model_check": model_check,
                "packet_path": str(packet_path),
                "output_path": str(output_path),
                "tmux_session": tmux_session,
                "session_dir": str(session_dir),
                "attach_instructions": pi_plan_attach_instructions(tmux_session, session_dir),
                "recovered_from_session_log": True,
            }
        )
        return

    timed_out = tmux_has_session(tmux_session)
    emit_json(
        {
            "status": "failed",
            "reason": "timeout_waiting_for_plan_artifact" if timed_out else "missing_plan_artifact",
            "harness": "pi",
            "model": model,
            "model_check": model_check,
            "packet_path": str(packet_path),
            "output_path": str(output_path),
            "tmux_session": tmux_session,
            "session_dir": str(session_dir),
            "attach_instructions": pi_plan_attach_instructions(tmux_session, session_dir),
        }
    )
    raise SystemExit(2)
