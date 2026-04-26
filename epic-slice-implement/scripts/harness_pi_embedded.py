#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4


PiEmbeddedSessionState = Literal[
    "unavailable",
    "idle",
    "processing",
    "awaiting_input",
    "closed",
    "failed",
]

STATE_PERSIST_MIN_INTERVAL_SECONDS = 0.5


@dataclass(frozen=True)
class PiEmbeddedCapabilities:
    available: bool
    reason: str
    protocol: str | None = None
    cli_path: str | None = None
    cli_supports_rpc: bool = False
    supports_events: bool = False
    supports_steer: bool = False
    supports_follow_up: bool = False
    supports_persistent_session: bool = False
    supports_session_switch: bool = False
    supports_session_stats: bool = False

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PiEmbeddedSessionSnapshot:
    session_id: str | None
    state: PiEmbeddedSessionState
    capabilities: PiEmbeddedCapabilities
    events: list[dict[str, object]]
    session_file: str | None = None
    session_dir: str | None = None
    protocol: str | None = None
    process_id: int | None = None
    fallback_reason: str | None = None

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


class PiEmbeddedSessionAdapter:
    """Harness-boundary facade for Pi RPC JSONL sessions."""

    def __init__(
        self,
        *,
        root: Path,
        session_dir: Path | None = None,
        model: str | None = None,
        title: str | None = None,
        session_snapshot: dict[str, object] | None = None,
    ) -> None:
        self.root = root
        self.session_dir = Path(
            session_dir
            or _string_value(session_snapshot, "session_dir")
            or (root / ".pm-dawn" / "ops" / "pi-embedded")
        )
        self.model = model
        self.title = title

    def capabilities(self) -> PiEmbeddedCapabilities:
        return detect_capabilities(self.root)

    def create(self) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        existing = _snapshot_from_state(self.session_dir, capabilities=capabilities)
        if existing and existing.state not in {"closed", "failed"} and _process_alive(existing.process_id):
            return existing

        process = _start_runner(
            root=self.root,
            session_dir=self.session_dir,
            model=self.model,
            title=self.title,
            capabilities=capabilities,
        )
        snapshot = PiEmbeddedSessionSnapshot(
            session_id=None,
            state="idle",
            capabilities=capabilities,
            events=[{"type": "runner_start", "process_id": process.pid}],
            session_dir=str(self.session_dir),
            protocol=capabilities.protocol,
            process_id=process.pid,
        )
        return snapshot

    def submit(self, prompt: str) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        snapshot = self.create()
        if snapshot.state == "unavailable":
            return snapshot
        _queue_command(self.session_dir, {"type": "prompt", "message": prompt})
        return _snapshot_with_event(
            self.session_dir,
            fallback=snapshot,
            state="processing",
            event={"type": "prompt_queued"},
            persist=False,
        )

    def observe(self) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        snapshot = _snapshot_from_state(self.session_dir, capabilities=capabilities)
        if snapshot is None:
            return PiEmbeddedSessionSnapshot(
                session_id=None,
                state="failed",
                capabilities=capabilities,
                events=[],
                session_dir=str(self.session_dir),
                protocol=capabilities.protocol,
                fallback_reason="embedded Pi session metadata was not found; relaunch the embedded session",
            )
        if snapshot.process_id and not _process_alive(snapshot.process_id) and snapshot.state == "processing":
            snapshot = _snapshot_with_event(
                self.session_dir,
                fallback=snapshot,
                state="failed",
                event={"type": "runner_missing", "process_id": snapshot.process_id},
                fallback_reason="embedded Pi runner process is no longer running",
            )
        return snapshot

    def steer(self, message: str) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        if not capabilities.supports_steer:
            return PiEmbeddedSessionSnapshot(
                session_id=None,
                state="unavailable",
                capabilities=capabilities,
                events=[],
                session_dir=str(self.session_dir),
                protocol=capabilities.protocol,
                fallback_reason="embedded Pi steering is not supported; use artifact-driven revision relaunch",
            )
        snapshot = self.observe()
        if snapshot.state in {"unavailable", "failed", "closed"}:
            return snapshot
        _queue_command(self.session_dir, {"type": "steer", "message": message})
        return _snapshot_with_event(
            self.session_dir,
            fallback=snapshot,
            state="processing",
            event={"type": "steer_queued"},
            persist=False,
        )

    def follow_up(self, message: str) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        if not capabilities.supports_follow_up:
            return PiEmbeddedSessionSnapshot(
                session_id=None,
                state="unavailable",
                capabilities=capabilities,
                events=[],
                session_dir=str(self.session_dir),
                protocol=capabilities.protocol,
                fallback_reason="embedded Pi follow-up is not supported; use artifact-driven revision relaunch",
            )
        snapshot = self.observe()
        if snapshot.state in {"unavailable", "failed", "closed"}:
            return snapshot
        _queue_command(self.session_dir, {"type": "follow_up", "message": message})
        return _snapshot_with_event(
            self.session_dir,
            fallback=snapshot,
            state="awaiting_input",
            event={"type": "follow_up_queued"},
            persist=False,
        )

    def close(self) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        snapshot = self.observe()
        if snapshot.state in {"failed", "closed", "unavailable"}:
            return snapshot
        _queue_command(self.session_dir, {"type": "close"})
        if snapshot.process_id and _process_alive(snapshot.process_id):
            try:
                os.kill(snapshot.process_id, signal.SIGTERM)
            except OSError:
                pass
        return _snapshot_with_event(
            self.session_dir,
            fallback=snapshot,
            state="closed",
            event={"type": "close_queued"},
            persist=False,
        )


def detect_capabilities(root: Path) -> PiEmbeddedCapabilities:
    _ = root
    cli_path = shutil.which("pi")
    if not cli_path:
        return PiEmbeddedCapabilities(
            available=False,
            reason="pi CLI was not found; fall back to the existing Pi CLI/tmux artifact loop",
        )

    help_text = _pi_help_text(cli_path)
    if help_text is None:
        return PiEmbeddedCapabilities(
            available=False,
            reason="pi CLI help could not be inspected; fall back to the existing Pi CLI/tmux artifact loop",
            cli_path=cli_path,
        )

    supports_rpc = "--mode <mode>" in help_text and "rpc" in help_text
    supports_session_dir = "--session-dir <dir>" in help_text
    supports_session_file = "--session <path>" in help_text
    supports_resume = "--resume" in help_text or "--continue" in help_text
    if not supports_rpc:
        return PiEmbeddedCapabilities(
            available=False,
            reason="pi CLI does not advertise --mode rpc; fall back to the existing Pi CLI/tmux artifact loop",
            cli_path=cli_path,
        )

    return PiEmbeddedCapabilities(
        available=True,
        reason="Pi RPC JSONL session surface is available",
        protocol="pi-rpc-jsonl",
        cli_path=cli_path,
        cli_supports_rpc=True,
        supports_events=True,
        supports_steer=True,
        supports_follow_up=True,
        supports_persistent_session=supports_session_dir and (supports_session_file or supports_resume),
        supports_session_switch=supports_session_file,
        supports_session_stats=True,
    )


def unavailable_snapshot(capabilities: PiEmbeddedCapabilities | None = None) -> PiEmbeddedSessionSnapshot:
    resolved = capabilities or detect_capabilities(Path.cwd())
    return PiEmbeddedSessionSnapshot(
        session_id=None,
        state="unavailable",
        capabilities=resolved,
        events=[],
        protocol=resolved.protocol,
        fallback_reason=resolved.reason,
    )


def _pi_help_text(cli_path: str) -> str | None:
    env = os.environ.copy()
    env.setdefault("PI_OFFLINE", "1")
    try:
        result = subprocess.run(
            [cli_path, "--help"],
            check=False,
            capture_output=True,
            env=env,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return f"{result.stdout}\n{result.stderr}"


def _state_path(session_dir: Path) -> Path:
    return session_dir / "embedded-state.json"


def _control_path(session_dir: Path) -> Path:
    return session_dir / "embedded-control.jsonl"


def _events_path(session_dir: Path) -> Path:
    return session_dir / "embedded-events.jsonl"


def _runner_log_path(session_dir: Path) -> Path:
    return session_dir / "embedded-runner.log"


def _string_value(payload: dict[str, object] | None, key: str) -> str | None:
    if not payload:
        return None
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _start_runner(
    *,
    root: Path,
    session_dir: Path,
    model: str | None,
    title: str | None,
    capabilities: PiEmbeddedCapabilities,
) -> subprocess.Popen[bytes]:
    args = [
        sys.executable,
        str(Path(__file__).resolve()),
        "runner",
        "--root",
        str(root),
        "--session-dir",
        str(session_dir),
    ]
    if model:
        args += ["--model", model]
    if title:
        args += ["--title", title]
    env = os.environ.copy()
    env.setdefault("PI_OFFLINE", "0")
    log = _runner_log_path(session_dir).open("ab")
    try:
        process = subprocess.Popen(
            args,
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        return process
    except OSError as exc:
        snapshot = PiEmbeddedSessionSnapshot(
            session_id=None,
            state="failed",
            capabilities=capabilities,
            events=[{"type": "runner_start_failed", "error": str(exc)}],
            session_dir=str(session_dir),
            protocol=capabilities.protocol,
            fallback_reason=f"embedded Pi runner could not be started: {exc}",
        )
        _write_snapshot(session_dir, snapshot)
        raise
    finally:
        log.close()


def _queue_command(session_dir: Path, command: dict[str, object]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    payload = {"id": f"pm-dawn-{uuid4().hex}", **command, "queued_at": time.time()}
    with _control_path(session_dir).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _snapshot_from_state(
    session_dir: Path,
    *,
    capabilities: PiEmbeddedCapabilities,
) -> PiEmbeddedSessionSnapshot | None:
    path = _state_path(session_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return PiEmbeddedSessionSnapshot(
            session_id=None,
            state="failed",
            capabilities=capabilities,
            events=[],
            session_dir=str(session_dir),
            protocol=capabilities.protocol,
            fallback_reason="embedded Pi session state could not be decoded",
        )
    return _snapshot_from_payload(payload, capabilities=capabilities)


def _snapshot_from_payload(
    payload: dict[str, object],
    *,
    capabilities: PiEmbeddedCapabilities,
) -> PiEmbeddedSessionSnapshot:
    state = payload.get("state")
    if state not in {"unavailable", "idle", "processing", "awaiting_input", "closed", "failed"}:
        state = "failed"
    events = payload.get("events")
    return PiEmbeddedSessionSnapshot(
        session_id=_string_value(payload, "session_id"),
        state=state,  # type: ignore[arg-type]
        capabilities=capabilities,
        events=events if isinstance(events, list) else [],
        session_file=_string_value(payload, "session_file"),
        session_dir=_string_value(payload, "session_dir"),
        protocol=_string_value(payload, "protocol") or capabilities.protocol,
        process_id=payload.get("process_id") if isinstance(payload.get("process_id"), int) else None,
        fallback_reason=_string_value(payload, "fallback_reason"),
    )


def _write_snapshot(session_dir: Path, snapshot: PiEmbeddedSessionSnapshot) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(session_dir)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temp_path.write_text(
        json.dumps(snapshot.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def _read_events(session_dir: Path, limit: int = 20) -> list[dict[str, object]]:
    path = _events_path(session_dir)
    if not path.exists():
        return []
    events: deque[dict[str, object]] = deque(maxlen=limit)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return list(events)


def _bounded_events(events: list[dict[str, object]], event: dict[str, object], limit: int = 20) -> list[dict[str, object]]:
    return [*events, event][-limit:]


def _append_event(
    session_dir: Path,
    event: dict[str, object],
    *,
    events: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    session_dir.mkdir(parents=True, exist_ok=True)
    recorded = {"time": time.time(), **event}
    with _events_path(session_dir).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(recorded, sort_keys=True) + "\n")
    if events is not None:
        return _bounded_events(events, recorded)
    return _read_events(session_dir)


def _snapshot_with_event(
    session_dir: Path,
    *,
    fallback: PiEmbeddedSessionSnapshot,
    state: PiEmbeddedSessionState,
    event: dict[str, object],
    fallback_reason: str | None = None,
    persist: bool = True,
) -> PiEmbeddedSessionSnapshot:
    events = _append_event(session_dir, event, events=fallback.events)
    snapshot = PiEmbeddedSessionSnapshot(
        session_id=fallback.session_id,
        state=state,
        capabilities=fallback.capabilities,
        events=events,
        session_file=fallback.session_file,
        session_dir=fallback.session_dir or str(session_dir),
        protocol=fallback.protocol,
        process_id=fallback.process_id,
        fallback_reason=fallback_reason,
    )
    if persist:
        _write_snapshot(session_dir, snapshot)
    return snapshot


def _runner_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a PM Dawn embedded Pi RPC session worker.")
    parser.add_argument("command", choices=("runner",))
    parser.add_argument("--root", required=True)
    parser.add_argument("--session-dir", required=True)
    parser.add_argument("--model")
    parser.add_argument("--title")
    return parser.parse_args()


def _runner_main() -> None:
    args = _runner_args()
    root = Path(args.root).resolve()
    session_dir = Path(args.session_dir).resolve()
    capabilities = detect_capabilities(root)
    if not capabilities.available or not capabilities.cli_path:
        _write_snapshot(session_dir, unavailable_snapshot(capabilities))
        return

    cmd = [capabilities.cli_path, "--mode", "rpc", "--session-dir", str(session_dir)]
    if args.model:
        cmd += ["--model", args.model]
    process = subprocess.Popen(
        cmd,
        cwd=str(root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    runner_pid = os.getpid()
    initial = PiEmbeddedSessionSnapshot(
        session_id=None,
        state="idle",
        capabilities=capabilities,
        events=_append_event(session_dir, {"type": "runner_ready", "process_id": runner_pid}, events=[]),
        session_dir=str(session_dir),
        protocol=capabilities.protocol,
        process_id=runner_pid,
    )
    _write_snapshot(session_dir, initial)
    state_lock = threading.Lock()
    state_holder = {"snapshot": initial, "last_persisted": time.time()}
    if args.title:
        _write_rpc_command(process, {"type": "set_session_name", "name": args.title})
    _write_rpc_command(process, {"type": "get_state"})

    def update_snapshot_from_event(event: dict[str, object], *, state: PiEmbeddedSessionState | None = None) -> None:
        with state_lock:
            current = state_holder["snapshot"]
            assert isinstance(current, PiEmbeddedSessionSnapshot)
            state_holder["snapshot"] = _snapshot_with_event(
                session_dir,
                fallback=current,
                state=state or current.state,
                event=event,
                persist=True,
            )
            state_holder["last_persisted"] = time.time()

    def read_stdout() -> None:
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                update_snapshot_from_event({"type": "non_json_stdout", "text": line[-500:]})
                continue
            event_type = payload.get("type")
            now = time.time()
            with state_lock:
                current = state_holder["snapshot"]
                assert isinstance(current, PiEmbeddedSessionSnapshot)
                should_persist = (
                    event_type not in {"message_update", "tool_execution_update"}
                    or now - float(state_holder["last_persisted"]) >= STATE_PERSIST_MIN_INTERVAL_SECONDS
                )
                state_holder["snapshot"] = _handle_rpc_output(
                    session_dir,
                    capabilities,
                    payload,
                    current,
                    runner_pid,
                    persist=should_persist,
                )
                if should_persist:
                    state_holder["last_persisted"] = now

    def read_stderr() -> None:
        assert process.stderr is not None
        for raw_line in process.stderr:
            line = raw_line.strip()
            if line:
                update_snapshot_from_event({"type": "stderr", "text": line[-500:]})

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    control_position = 0
    control_remainder = ""
    try:
        while process.poll() is None:
            control = _control_path(session_dir)
            if control.exists():
                with control.open(encoding="utf-8") as handle:
                    handle.seek(control_position)
                    chunk = handle.read()
                    control_position = handle.tell()
                if chunk:
                    text = f"{control_remainder}{chunk}"
                    lines = text.splitlines()
                    if text.endswith("\n"):
                        control_remainder = ""
                    else:
                        control_remainder = lines.pop() if lines else text
                    for line in lines:
                        with state_lock:
                            current = state_holder["snapshot"]
                            assert isinstance(current, PiEmbeddedSessionSnapshot)
                            state_holder["snapshot"] = _send_runner_command(session_dir, process, line, current)
                            state_holder["last_persisted"] = time.time()
            time.sleep(0.25)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        exit_code = process.poll()
        with state_lock:
            current = state_holder["snapshot"]
            assert isinstance(current, PiEmbeddedSessionSnapshot)
            state_holder["snapshot"] = _snapshot_with_event(
                session_dir,
                fallback=current,
                state="closed" if exit_code == 0 else "failed",
                event={"type": "runner_exit", "exit_code": exit_code},
                fallback_reason=None if exit_code == 0 else "embedded Pi RPC process exited unexpectedly",
            )


def _send_runner_command(
    session_dir: Path,
    process: subprocess.Popen[str],
    line: str,
    current: PiEmbeddedSessionSnapshot,
) -> PiEmbeddedSessionSnapshot:
    try:
        command = json.loads(line)
    except json.JSONDecodeError:
        return _snapshot_with_event(
            session_dir,
            fallback=current,
            state=current.state,
            event={"type": "bad_control_line"},
        )
    command_type = command.get("type")
    if command_type == "close":
        process.terminate()
        return _snapshot_with_event(
            session_dir,
            fallback=current,
            state="closed",
            event={"type": "close_sent", "id": command.get("id")},
        )
    if command_type not in {"prompt", "steer", "follow_up"}:
        return _snapshot_with_event(
            session_dir,
            fallback=current,
            state=current.state,
            event={"type": "unsupported_control_command", "command": command_type},
        )
    rpc_command = {
        "id": command.get("id"),
        "type": command_type,
        "message": command.get("message", ""),
    }
    if not _write_rpc_command(process, rpc_command):
        return _snapshot_with_event(
            session_dir,
            fallback=current,
            state="failed",
            event={"type": "stdin_unavailable", "command": command_type},
            fallback_reason="embedded Pi RPC stdin is unavailable",
        )
    snapshot = _snapshot_with_event(
        session_dir,
        fallback=current,
        state="processing" if command_type in {"prompt", "steer"} else "awaiting_input",
        event={"type": f"{command_type}_sent", "id": command.get("id")},
    )
    _write_rpc_command(process, {"type": "get_state"})
    return snapshot


def _write_rpc_command(process: subprocess.Popen[str], command: dict[str, object]) -> bool:
    if process.stdin is None:
        return False
    process.stdin.write(json.dumps(command, sort_keys=True) + "\n")
    process.stdin.flush()
    return True


def _handle_rpc_output(
    session_dir: Path,
    capabilities: PiEmbeddedCapabilities,
    payload: dict[str, object],
    current: PiEmbeddedSessionSnapshot,
    runner_pid: int,
    *,
    persist: bool,
) -> PiEmbeddedSessionSnapshot:
    event_type = payload.get("type")
    events = _append_event(session_dir, _summarize_rpc_payload(payload), events=current.events)
    state = current.state
    session_id = current.session_id
    session_file = current.session_file
    fallback_reason = None
    if event_type == "agent_start":
        state = "processing"
    elif event_type == "agent_end":
        state = "idle"
    elif event_type == "queue_update":
        state = "awaiting_input"
    elif event_type == "response" and payload.get("success") is False:
        state = "failed"
        fallback_reason = str(payload.get("error") or "Pi RPC command failed")
    if event_type == "response" and payload.get("command") == "get_state" and isinstance(payload.get("data"), dict):
        data = payload["data"]
        session_id = _string_value(data, "sessionId") or session_id
        session_file = _string_value(data, "sessionFile") or session_file
        if data.get("isStreaming") is True:
            state = "processing"
        elif data.get("pendingMessageCount"):
            state = "awaiting_input"
        else:
            state = "idle"
    snapshot = PiEmbeddedSessionSnapshot(
        session_id=session_id,
        state=state,
        capabilities=capabilities,
        events=events,
        session_file=session_file,
        session_dir=str(session_dir),
        protocol=capabilities.protocol,
        process_id=runner_pid,
        fallback_reason=fallback_reason,
    )
    if persist:
        _write_snapshot(session_dir, snapshot)
    return snapshot


def _summarize_rpc_payload(payload: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {"type": payload.get("type", "unknown")}
    for key in ("command", "success", "id"):
        if key in payload:
            summary[key] = payload[key]
    if payload.get("type") in {"agent_start", "agent_end", "turn_start", "turn_end", "message_start", "message_end"}:
        return summary
    if payload.get("type") == "message_update":
        update = payload.get("assistantMessageEvent")
        if isinstance(update, dict):
            summary["assistant_event_type"] = update.get("type")
    if payload.get("type") == "tool_execution_start":
        summary["tool"] = payload.get("toolName")
    if payload.get("type") == "tool_execution_end":
        summary["tool"] = payload.get("toolName")
    if payload.get("type") == "response" and payload.get("success") is False:
        summary["error"] = payload.get("error")
    return summary


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "runner":
        _runner_main()
