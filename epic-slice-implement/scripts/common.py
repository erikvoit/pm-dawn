#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.implement import (
    build_launch_prompt,
    build_steer_prompt,
    load_execution_input,
    resolve_agent_harness,
    resolve_approved_plan_path,
    resolve_harness_model,
)
from pm_dawn_core.layout import (
    compiled_packet_json_path,
    implementation_plan_artifact_path,
    legacy_opencode_plan_artifact_path,
    packet_markdown_path,
    reviewed_plan_artifact_path,
    run_artifact_path,
    run_metadata_path,
    slice_markdown_path,
)
from pm_dawn_core.profile import repo_root
from pm_dawn_core.runtime import (
    check_active_harness_model,
    command_available,
    opencode_config_path,
    pi_models_config_path,
    provider_timeout_seconds,
    require_cli,
    resolved_shell_executable,
    run_cmd,
    runtime_home,
    tmux_has_session,
)


def emit_json(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def sanitize_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-") or "session"


def slice_title(epic_key: str, group_id: str, phase: str | None = None, packet_id: str | None = None) -> str:
    base = f"slice:{epic_key}:{packet_id or group_id}"
    if phase == "planning":
        return f"{base}:plan-first"
    if phase == "implementing":
        return f"{base}:implement-from-plan"
    return base


def ensure_pm_dawn_ignored(
    root: Path,
    *,
    create_gitignore: bool = False,
    dry_run: bool = False,
) -> dict:
    entry = ".pm-dawn/"
    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8").splitlines()
        if entry in content:
            return {"status": "already_ignored", "path": str(gitignore)}
        text = gitignore.read_text(encoding="utf-8")
        if dry_run:
            return {"status": "would_add_to_gitignore", "path": str(gitignore)}
        suffix = "" if text.endswith("\n") or text == "" else "\n"
        gitignore.write_text(text + suffix + entry + "\n", encoding="utf-8")
        return {"status": "added_to_gitignore", "path": str(gitignore)}
    if create_gitignore and (root / ".git").exists():
        if dry_run:
            return {"status": "would_create_gitignore", "path": str(gitignore)}
        gitignore.write_text(entry + "\n", encoding="utf-8")
        return {"status": "created_gitignore", "path": str(gitignore)}
    exclude = root / ".git" / "info" / "exclude"
    if exclude.exists():
        content = exclude.read_text(encoding="utf-8").splitlines()
        if entry not in content:
            text = exclude.read_text(encoding="utf-8")
            if dry_run:
                return {"status": "would_add_to_git_info_exclude", "path": str(exclude)}
            suffix = "" if text.endswith("\n") or text == "" else "\n"
            exclude.write_text(text + suffix + entry + "\n", encoding="utf-8")
            return {"status": "added_to_git_info_exclude", "path": str(exclude)}
        return {"status": "already_ignored", "path": str(exclude)}
    git_dir = root / ".git"
    if not git_dir.exists():
        return {"status": "not_git_repo", "path": None}
    return {"status": "unprotected", "path": None}


def opencode_server_session_name(root: Path) -> str:
    return f"opencode-server-{sanitize_name(root.name)}"


def pi_slice_tmux_session_name(epic_key: str, group_id: str, packet_id: str | None = None) -> str:
    return f"pi-{sanitize_name(epic_key)}-{sanitize_name(packet_id or group_id)}"


def opencode_slice_tmux_session_name(epic_key: str, group_id: str, packet_id: str | None = None) -> str:
    return f"opencode-{sanitize_name(epic_key)}-{sanitize_name(packet_id or group_id)}"


def pi_session_dir(root: Path, epic_key: str, group_id: str, packet_id: str | None = None, phase: str | None = None) -> Path:
    leaf = sanitize_name(packet_id or group_id)
    phase_leaf = sanitize_name(phase or "implementing")
    return root / ".pm-dawn" / "epics" / epic_key / "ops" / "runs" / "pi-sessions" / leaf / phase_leaf


def pi_console_log_path(session_dir: Path) -> Path:
    return session_dir / "console.log"


def _shell_command(script: str) -> list[str]:
    return [resolved_shell_executable(), "-lc", script]


def launch_tmux_session_with_tail(
    *,
    session_name: str,
    cwd: Path,
    runner_script: str,
    tail_script: str,
) -> None:
    require_cli("tmux")
    run_cmd(["tmux", "new-session", "-d", "-s", session_name, "-c", str(cwd), *_shell_command(runner_script)])
    run_cmd(["tmux", "split-window", "-v", "-t", f"{session_name}:0", "-c", str(cwd), *_shell_command(tail_script)])
    run_cmd(["tmux", "select-layout", "-t", f"{session_name}:0", "even-vertical"])


def pi_runner_script(*, root: Path, session_dir: Path, command: str) -> str:
    console_log = pi_console_log_path(session_dir)
    shell_executable = resolved_shell_executable()
    shell_path = shlex.quote(shell_executable)
    shell_name = Path(shell_executable).name.lower()
    if "zsh" in shell_name:
        status_capture = 'runner_exit=${pipestatus[1]:-0}; '
    elif "bash" in shell_name:
        status_capture = 'runner_exit=${PIPESTATUS[0]:-0}; '
    else:
        # Generic POSIX shells do not expose pipeline segment statuses.
        status_capture = 'runner_exit=${?:-0}; '
    return (
        f"cd {shlex.quote(str(root))} && "
        f"mkdir -p {shlex.quote(str(session_dir))} && "
        "export PYTHONUNBUFFERED=1 && "
        f"{{ {command}; }} 2>&1 | tee -a {shlex.quote(str(console_log))}; "
        f"{status_capture}"
        'printf "\\n[pm-dawn] runner exited with status %s\\n" "$runner_exit"; '
        f"exec {shell_path} -i"
    )


def pi_tail_script(*, session_dir: Path) -> str:
    session_dir_quoted = shlex.quote(str(session_dir))
    return (
        f"mkdir -p {session_dir_quoted} && "
        'echo "[pm-dawn] waiting for pi session log..." && '
        "while true; do "
        f"file=$(find {session_dir_quoted} -maxdepth 1 -type f -name '*.jsonl' | head -n 1); "
        'if [ -n "$file" ]; then '
        'echo "[pm-dawn] tailing $file"; '
        'tail -n +1 -F "$file"; '
        "break; "
        "fi; "
        "sleep 1; "
        "done"
    )


def list_sessions_json(max_count: int = 50) -> list[dict]:
    proc = run_cmd(["opencode", "session", "list", "--format", "json", "--max-count", str(max_count)])
    data = json.loads(proc.stdout or "[]")
    return data if isinstance(data, list) else []


def latest_session_by_title(title: str) -> dict | None:
    matches = [item for item in list_sessions_json() if item.get("title") == title]
    if not matches:
        return None
    matches.sort(key=lambda item: item.get("time", {}).get("updated", 0), reverse=True)
    return matches[0]


def attach_instructions(server_url: str | None, session_id: str | None, tmux_session: str | None, root: Path) -> list[str]:
    instructions: list[str] = []
    if tmux_session:
        instructions.append(f"tmux attach -t {tmux_session}")
    if server_url:
        cmd = f"opencode attach {server_url} --dir {root}"
        if session_id:
            cmd += f" --session {session_id}"
        instructions.append(cmd)
    return instructions


def pi_attach_instructions(tmux_session: str | None) -> list[str]:
    instructions: list[str] = []
    if tmux_session:
        instructions.append(f"tmux attach -t {tmux_session}")
        instructions.append(f"tmux list-panes -t {tmux_session} -F '#{{pane_index}} #{{pane_current_command}}'")
        instructions.append(f"tmux select-pane -t {tmux_session}:0.1")
    return instructions


def poll_for_session(title: str, timeout_seconds: int = 30) -> dict | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        found = latest_session_by_title(title)
        if found:
            return found
        time.sleep(1)
    return None


def export_session_json(session_id: str) -> dict:
    proc = run_cmd(["opencode", "export", session_id])
    stdout = proc.stdout.strip()
    start = stdout.find("{")
    if start == -1:
        raise RuntimeError(f"could not parse opencode export output for session {session_id}")
    try:
        return json.loads(stdout[start:])
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"could not decode opencode export output for session {session_id}: {exc}"
        ) from exc


def infer_phase(run_meta: dict, session_export: dict | None = None) -> str:
    explicit = run_meta.get("phase")
    if explicit:
        return explicit
    title = ""
    if session_export:
        title = session_export.get("info", {}).get("title", "")
    if "plan-first" in title:
        return "planning"
    if run_meta.get("last_action") == "prepare":
        return "planning"
    return "implementing"


def latest_completed_assistant_message(session_export: dict, *, require_text: bool = False) -> dict | None:
    assistants = [msg for msg in session_export.get("messages", []) if msg.get("info", {}).get("role") == "assistant"]
    completed = [msg for msg in assistants if msg.get("info", {}).get("time", {}).get("completed")]
    if require_text:
        completed = [msg for msg in completed if message_text(msg)]
    if not completed:
        return None
    completed.sort(key=lambda msg: msg.get("info", {}).get("time", {}).get("completed", 0))
    return completed[-1]


def latest_assistant_message(session_export: dict) -> dict | None:
    assistants = [msg for msg in session_export.get("messages", []) if msg.get("info", {}).get("role") == "assistant"]
    if not assistants:
        return None
    return assistants[-1]


def session_completion_state(session_export: dict) -> str:
    latest = latest_assistant_message(session_export)
    if not latest:
        return "in_progress"
    if not latest.get("info", {}).get("time", {}).get("completed"):
        return "in_progress"
    error = latest.get("info", {}).get("error", {})
    message = str(error.get("data", {}).get("message", "")).lower()
    if "timed out" in message:
        return "timed_out"
    finish = latest.get("info", {}).get("finish")
    if finish == "stop":
        return "completed"
    if finish == "tool-calls":
        return "failed"
    return "failed"


def session_runtime_status(run_meta: dict, completion_state: str) -> str:
    if completion_state == "completed":
        return "completed"
    if completion_state in {"failed", "timed_out"}:
        return completion_state
    runtime = run_meta.get("runtime", {})
    tmux_session = runtime.get("tmux_session") or run_meta.get("opencode", {}).get("tmux_session")
    server_tmux_session = runtime.get("server_tmux_session") or run_meta.get("opencode", {}).get("server_tmux_session")
    if tmux_session and tmux_has_session(tmux_session):
        return "running"
    if server_tmux_session and tmux_has_session(server_tmux_session):
        return "running"
    return "stopped"


def message_text(message: dict) -> str:
    texts: list[str] = []
    for part in message.get("parts", []):
        if part.get("type") == "text":
            text = part.get("text", "")
            if text:
                texts.append(text)
    return "\n".join(texts).strip()


def render_phase_artifact(
    *,
    epic_key: str,
    group_id: str,
    phase: str,
    session_export: dict,
    source_message: dict,
) -> str:
    session_info = session_export.get("info", {})
    completed_at = source_message.get("info", {}).get("time", {}).get("completed")
    body = message_text(source_message) or "(No assistant text captured.)"
    title = "Approved Plan" if phase == "planning" else "Implementation Result"
    lines = [
        f"# {epic_key} / {group_id} / {title}",
        "",
        f"- Phase: {phase}",
        f"- Session ID: {session_info.get('id')}",
        f"- Session Title: {session_info.get('title')}",
    ]
    if completed_at:
        lines.append(f"- Completed: {completed_at}")
    lines += [
        "",
        "## Captured Output",
        "",
        body,
        "",
    ]
    return "\n".join(lines)
