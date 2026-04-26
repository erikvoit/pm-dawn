#!/usr/bin/env python3
from __future__ import annotations

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
    supports_events: bool = False
    supports_steer: bool = False
    supports_follow_up: bool = False
    supports_persistent_session: bool = False

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PiEmbeddedSessionSnapshot:
    session_id: str | None
    state: PiEmbeddedSessionState
    capabilities: PiEmbeddedCapabilities
    events: list[dict[str, object]]
    fallback_reason: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "capabilities": self.capabilities.to_payload(),
            "events": self.events,
            "fallback_reason": self.fallback_reason,
        }


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
    return PiEmbeddedCapabilities(
        available=False,
        reason=(
            "embedded Pi SDK/session surface has not been verified; "
            "fall back to the existing Pi CLI/tmux artifact loop"
        ),
    )


def unavailable_snapshot(capabilities: PiEmbeddedCapabilities | None = None) -> PiEmbeddedSessionSnapshot:
    resolved = capabilities or detect_capabilities(Path.cwd())
    return PiEmbeddedSessionSnapshot(
        session_id=None,
        state="unavailable",
        capabilities=resolved,
        events=[],
        fallback_reason=resolved.reason,
    )
