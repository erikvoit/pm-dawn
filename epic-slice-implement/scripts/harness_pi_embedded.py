#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


PiEmbeddedSessionState = Literal[
    "unavailable",
    "idle",
    "processing",
    "awaiting_input",
    "closed",
    "failed",
]


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
    """Harness-boundary facade for a future Pi embedded session integration."""

    def __init__(self, *, root: Path) -> None:
        self.root = root

    def capabilities(self) -> PiEmbeddedCapabilities:
        return detect_capabilities(self.root)

    def create(self) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        raise NotImplementedError("embedded Pi sessions are not wired yet")

    def submit(self, prompt: str) -> PiEmbeddedSessionSnapshot:
        _ = prompt
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        raise NotImplementedError("embedded Pi submit is not wired yet")

    def observe(self) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        raise NotImplementedError("embedded Pi observation is not wired yet")

    def steer(self, message: str) -> PiEmbeddedSessionSnapshot:
        _ = message
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        if not capabilities.supports_steer:
            return PiEmbeddedSessionSnapshot(
                session_id=None,
                state="unavailable",
                capabilities=capabilities,
                events=[],
                fallback_reason="embedded Pi steering is not supported; use artifact-driven revision relaunch",
            )
        raise NotImplementedError("embedded Pi steering is not wired yet")

    def follow_up(self, message: str) -> PiEmbeddedSessionSnapshot:
        _ = message
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        if not capabilities.supports_follow_up:
            return PiEmbeddedSessionSnapshot(
                session_id=None,
                state="unavailable",
                capabilities=capabilities,
                events=[],
                fallback_reason="embedded Pi follow-up is not supported; use artifact-driven revision relaunch",
            )
        raise NotImplementedError("embedded Pi follow-up is not wired yet")

    def close(self) -> PiEmbeddedSessionSnapshot:
        capabilities = self.capabilities()
        if not capabilities.available:
            return unavailable_snapshot(capabilities)
        raise NotImplementedError("embedded Pi close is not wired yet")


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
        available=False,
        reason=(
            "Pi RPC JSONL session surface is detected, but PM Dawn embedded lifecycle wiring "
            "is not implemented yet; "
            "fall back to the existing Pi CLI/tmux artifact loop"
        ),
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
