from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path

from .layout import (
    compiled_packet_json_path,
    implementation_plan_artifact_path,
    legacy_opencode_plan_artifact_path,
    packet_markdown_path,
    packet_plan_artifacts,
    packet_plan_proposal_artifact_path,
    packet_plan_response_artifact_path,
    packet_plan_review_artifact_path,
    packet_plan_review_state_path,
    run_artifact_path,
    slice_markdown_path,
)
from .markdown import parse_packet_markdown, parse_slice_markdown
from .profile import (
    load_project_profile as load_core_project_profile,
    make_default_profile,
    repo_root,
)


REQUIRED_HANDOFF_FIELDS = [
    "schema_version",
    "epic_key",
    "group_id",
    "primary_issue",
    "secondary_issues",
    "goal",
    "branch_name",
    "pr_traceability",
    "entry_criteria",
    "exit_criteria",
    "repo_surfaces",
    "implementation_steps",
    "validation_steps",
    "risks",
    "open_questions",
    "source_context",
]

PACKET_PLAN_REVIEW_STATUSES = frozenset(
    {
        "proposal_submitted",
        "changes_requested",
        "response_submitted",
        "accepted",
        "rejected",
    }
)

PACKET_PLAN_WAITABLE_STATUSES = frozenset(
    {
        "proposal_submitted",
        "changes_requested",
        "response_submitted",
    }
)


@dataclass(frozen=True)
class ImplementCommandSurface:
    command_id: str
    script_name: str
    description: str
    compatibility_aliases: tuple[str, ...] = ()

    @property
    def relative_script_path(self) -> Path:
        return Path("epic-slice-implement") / "scripts" / self.script_name


@dataclass(frozen=True)
class PacketPlanReviewStateSnapshot:
    status: str
    current_artifact: Path | None
    submitted_artifact: Path | None
    proposal_artifact: Path
    review_artifact: Path
    response_artifact: Path
    implementation_plan_artifact: Path
    accepted_artifact: Path | None = None

    @property
    def requires_revision_run(self) -> bool:
        return self.status == "changes_requested"

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    @property
    def expected_artifact(self) -> Path | None:
        if self.status == "changes_requested":
            return self.response_artifact
        if self.status == "proposal_submitted":
            return self.proposal_artifact
        if self.status == "response_submitted":
            return self.response_artifact
        if self.status == "accepted":
            return self.implementation_plan_artifact
        return None


@dataclass(frozen=True)
class ImplementationReviewMonitorSnapshot:
    status: str
    completion_state: str | None
    review_ready: bool
    waitable: bool
    next_action: str
    implementation_plan_artifact: Path | None
    result_artifact: Path | None
    worker_status: str | None
    worker_note: str | None


IMPLEMENT_COMMAND_SURFACES = (
    ImplementCommandSurface(
        command_id="handoff",
        script_name="load_handoff.py",
        description="Load and validate a .pm-dawn slice or packet handoff.",
        compatibility_aliases=("load_handoff",),
    ),
    ImplementCommandSurface(
        command_id="prompt",
        script_name="build_opencode_prompt.py",
        description="Build the exact launch or steer prompt for an implementation run.",
        compatibility_aliases=("build_opencode_prompt",),
    ),
    ImplementCommandSurface(
        command_id="plan",
        script_name="generate_packet_implementation_plan.py",
        description="Generate a worker-authored packet plan proposal artifact.",
        compatibility_aliases=("generate_packet_implementation_plan",),
    ),
    ImplementCommandSurface(
        command_id="review-plan",
        script_name="coordinate_plan_review.py",
        description="Coordinate packet plan review, response, and acceptance state.",
        compatibility_aliases=("coordinate_plan_review",),
    ),
    ImplementCommandSurface(
        command_id="launch",
        script_name="launch_slice_session.py",
        description="Launch a planning or implementation session through the configured harness.",
        compatibility_aliases=("launch_slice_session",),
    ),
    ImplementCommandSurface(
        command_id="server",
        script_name="ensure_opencode_server.py",
        description="Ensure the OpenCode server runtime is available for launches.",
        compatibility_aliases=("ensure_opencode_server",),
    ),
    ImplementCommandSurface(
        command_id="status",
        script_name="slice_status.py",
        description="Report the current lifecycle status for a slice run.",
        compatibility_aliases=("slice_status",),
    ),
    ImplementCommandSurface(
        command_id="pending-review",
        script_name="mark_slice_pending_review.py",
        description="Mark a worker-owned slice run as pending human review.",
        compatibility_aliases=("mark_slice_pending_review",),
    ),
    ImplementCommandSurface(
        command_id="sync",
        script_name="sync_slice_session_state.py",
        description="Sync session state and optionally write captured run artifacts.",
        compatibility_aliases=("sync_slice_session_state",),
    ),
    ImplementCommandSurface(
        command_id="steer",
        script_name="steer_slice.py",
        description="Send steering guidance to an in-flight slice session.",
        compatibility_aliases=("steer_slice",),
    ),
    ImplementCommandSurface(
        command_id="cleanup",
        script_name="cleanup_slice_artifacts.py",
        description="Archive or delete artifacts for one slice.",
        compatibility_aliases=("cleanup_slice_artifacts",),
    ),
    ImplementCommandSurface(
        command_id="cleanup-by-name",
        script_name="cleanup_slice_by_name.py",
        description="Resolve a slice by group id and reuse the cleanup flow.",
        compatibility_aliases=("cleanup_slice_by_name",),
    ),
    ImplementCommandSurface(
        command_id="record-run",
        script_name="record_slice_run.py",
        description="Persist launch metadata for the current slice run.",
        compatibility_aliases=("record_slice_run",),
    ),
    ImplementCommandSurface(
        command_id="migrate-layout",
        script_name="migrate_pm_dawn_layout.py",
        description="Create or migrate the .pm-dawn workspace layout.",
        compatibility_aliases=("migrate_pm_dawn_layout",),
    ),
)


def resolve_implement_command(command: str) -> ImplementCommandSurface:
    normalized = command.strip().lower()
    for surface in IMPLEMENT_COMMAND_SURFACES:
        names = {surface.command_id, surface.script_name.removesuffix(".py"), *surface.compatibility_aliases}
        if normalized in names:
            return surface
    raise KeyError(f"unknown epic-slice-implement command surface: {command}")


def implement_command_relative_script_path(command: str) -> Path:
    return resolve_implement_command(command).relative_script_path


def render_implement_command(
    root: Path,
    command: str,
    *args: str,
    python_executable: str = "python",
) -> str:
    root = repo_root(root)
    script_path = root / implement_command_relative_script_path(command)
    relative = script_path.relative_to(root)
    return shlex.join([python_executable, relative.as_posix(), *args])


DEFAULT_PROJECT_PROFILE: dict = make_default_profile(
    {
        "monitoring": {
            "defaults": {
                "initial_session_check_seconds": 5,
                "planning_artifact_grace_period_seconds": 60,
                "implementation_artifact_grace_period_seconds": 120,
            },
            "pi": {},
            "opencode": {},
        },
        "agent_harness": {
            "default": "opencode",
        },
        "pi": {
            "default_model": "qwen/qwen3-coder-next-q6k",
        },
        "opencode": {
            "default_model": "llama/qwen/qwen3-coder-next",
        },
    }
)


def load_project_profile(root: Path) -> dict:
    return load_core_project_profile(root, DEFAULT_PROJECT_PROFILE)


def full_suite_command(root: Path) -> str:
    profile = load_project_profile(root)
    return str(profile.get("validation", {}).get("full_suite_command", "make check"))


def harness_monitoring_settings(root: Path, harness: str) -> dict[str, int]:
    profile = load_project_profile(root)
    monitoring = profile.get("monitoring", {})
    base_defaults = DEFAULT_PROJECT_PROFILE["monitoring"]["defaults"]
    defaults = monitoring.get("defaults", base_defaults)
    harness_overrides = monitoring.get(harness, {})
    legacy_overrides = {}
    if harness == "pi":
        legacy_overrides = profile.get("pi", {}).get("monitoring", {})
    elif harness == "opencode":
        legacy_overrides = profile.get("opencode", {}).get("monitoring", {})

    def resolve(name: str) -> int:
        value = harness_overrides.get(name, legacy_overrides.get(name, defaults[name]))
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return int(base_defaults[name])
        return parsed if parsed > 0 else int(base_defaults[name])

    return {
        "initial_session_check_seconds": resolve("initial_session_check_seconds"),
        "planning_artifact_grace_period_seconds": resolve("planning_artifact_grace_period_seconds"),
        "implementation_artifact_grace_period_seconds": resolve(
            "implementation_artifact_grace_period_seconds"
        ),
    }


def pi_monitoring_settings(root: Path) -> dict[str, int]:
    return harness_monitoring_settings(root, "pi")


def opencode_monitoring_settings(root: Path) -> dict[str, int]:
    return harness_monitoring_settings(root, "opencode")


def pi_initial_session_check_seconds(root: Path) -> int:
    return pi_monitoring_settings(root)["initial_session_check_seconds"]


def pi_planning_artifact_grace_period_seconds(root: Path) -> int:
    return pi_monitoring_settings(root)["planning_artifact_grace_period_seconds"]


def pi_implementation_artifact_grace_period_seconds(root: Path) -> int:
    return pi_monitoring_settings(root)["implementation_artifact_grace_period_seconds"]


def packet_type_from_id(packet_id: str | None) -> str | None:
    if not packet_id or "__" not in packet_id:
        return None
    suffix = packet_id.rsplit("__", 1)[-1]
    if "_" not in suffix:
        return None
    return suffix.split("_", 1)[1]


def resolve_agent_harness(
    root: Path,
    *,
    explicit_harness: str | None = None,
    phase: str | None = None,
) -> str:
    profile = load_project_profile(root)
    harness_config = profile.get("agent_harness", {})
    aliases = harness_config.get("aliases", {})

    def resolve_alias(value: str | None) -> str | None:
        if value is None:
            return None
        return str(aliases.get(value, value))

    if explicit_harness:
        return resolve_alias(explicit_harness) or explicit_harness

    phase_harnesses = harness_config.get("phase", {})
    if phase:
        phase_harness = resolve_alias(phase_harnesses.get(phase))
        if phase_harness:
            return phase_harness

    default_harness = resolve_alias(harness_config.get("default"))
    if default_harness:
        return default_harness
    return "opencode"


def resolve_harness_model(
    root: Path,
    *,
    harness: str,
    explicit_model: str | None = None,
    phase: str | None = None,
    packet_id: str | None = None,
) -> str:
    profile = load_project_profile(root)
    harness_config = profile.get(harness, {})
    aliases = harness_config.get("aliases", {})

    def resolve_alias(value: str | None) -> str | None:
        if value is None:
            return None
        return str(aliases.get(value, value))

    if explicit_model:
        return resolve_alias(explicit_model) or explicit_model

    phase_models = harness_config.get("phase_models", {})
    if phase:
        phase_model = resolve_alias(phase_models.get(phase))
        if phase_model:
            return phase_model

    packet_models = harness_config.get("packet_models", {})
    packet_type = packet_type_from_id(packet_id)
    if packet_type:
        packet_model = resolve_alias(packet_models.get(packet_type))
        if packet_model:
            return packet_model

    default_model = resolve_alias(harness_config.get("default_model"))
    if default_model:
        return default_model
    if harness == "pi":
        return "qwen/qwen3-coder-next-q6k"
    return "llama/qwen/qwen3-coder-next"


def validate_handoff(data: dict) -> None:
    missing = [field for field in REQUIRED_HANDOFF_FIELDS if field not in data]
    if missing:
        raise RuntimeError(f"handoff Markdown missing required fields: {', '.join(missing)}")


def load_handoff(root: Path, epic_key: str, group_id: str) -> tuple[dict, Path]:
    path = slice_markdown_path(root, epic_key, group_id)
    data = parse_slice_markdown(path)
    validate_handoff(data)
    return data, path


def compile_packet_handoff(root: Path, epic_key: str, group_id: str, packet_id: str) -> tuple[dict, Path]:
    handoff, _handoff_path = load_handoff(root, epic_key, group_id)
    packet_path = packet_markdown_path(root, epic_key, packet_id)
    packet = parse_packet_markdown(packet_path)
    if packet["packet_id"] != packet_id:
        raise RuntimeError(f"packet Markdown id mismatch: expected {packet_id}, found {packet['packet_id']}")

    payload = {
        "schema_version": "v1",
        "epic_key": epic_key,
        "group_id": group_id,
        "packet_id": packet_id,
        "packet_type": packet["packet_type"],
        "risk_class": packet["risk_class"],
        "recommended_executor": packet["recommended_executor"],
        "routing_notes": packet["routing_notes"],
        "primary_issue": packet["primary_issue"] or handoff["primary_issue"],
        "secondary_issues": packet["secondary_issues"] or handoff.get("secondary_issues", []),
        "goal": packet["goal"] or handoff["goal"],
        "branch_name": packet["branch_name"] or handoff["branch_name"],
        "pr_traceability": handoff["pr_traceability"],
        "entry_criteria": handoff["entry_criteria"],
        "exit_criteria": handoff["exit_criteria"],
        "repo_surfaces": handoff["repo_surfaces"],
        "implementation_steps": packet["implementation_steps"],
        "validation_steps": packet["validation_steps"] or handoff["validation_steps"],
        "risks": handoff.get("risks", []),
        "open_questions": packet["open_questions"],
        "source_context": {
            **handoff["source_context"],
            "packet_markdown": str(packet_path),
            "compiled_from": "packet_markdown",
            "depends_on": packet["depends_on"],
            "files_to_read": packet["files_to_read"],
            "files_to_change": packet["files_to_change"],
            "acceptance_checks": packet["acceptance_checks"],
            "constraints": packet["constraints"],
            "commit_scope_guidance": packet["commit_scope_guidance"],
            "risk_class": packet["risk_class"],
            "recommended_executor": packet["recommended_executor"],
            "routing_notes": packet["routing_notes"],
        },
    }
    output_path = compiled_packet_json_path(root, epic_key, packet_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload, output_path


def load_execution_input(root: Path, epic_key: str, group_id: str, packet_id: str | None = None) -> tuple[dict, Path]:
    root = repo_root(root)
    if not packet_id:
        return load_handoff(root, epic_key, group_id)
    data, output_path = compile_packet_handoff(root, epic_key, group_id, packet_id)
    validate_handoff(data)
    return data, output_path


def packet_plan_review_state_template(
    root: Path,
    epic_key: str,
    packet_id: str,
    *,
    status: str,
    proposal_path: Path | None = None,
    review_path: Path | None = None,
    response_path: Path | None = None,
    implementation_plan_path: Path | None = None,
) -> dict:
    root = repo_root(root)
    artifacts = packet_plan_artifacts(root, epic_key, packet_id)
    proposal = proposal_path or artifacts.proposal_md
    review = review_path or artifacts.review_md
    response = response_path or artifacts.response_md
    implementation = implementation_plan_path or artifacts.implementation_plan_md
    return {
        "schema_version": "v1",
        "epic_key": epic_key,
        "packet_id": packet_id,
        "status": status,
        "current_artifact": str(proposal.resolve()) if proposal.exists() or status == "proposal_submitted" else None,
        "proposal_artifact": str(proposal.resolve()),
        "review_artifact": str(review.resolve()) if review.exists() else None,
        "response_artifact": str(response.resolve()) if response.exists() else None,
        "implementation_plan_artifact": str(implementation.resolve()) if implementation.exists() else None,
    }


def resolve_packet_plan_review_state(root: Path, epic_key: str, packet_id: str) -> dict | None:
    path = packet_plan_review_state_path(root, epic_key, packet_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def packet_plan_review_state_snapshot(
    root: Path,
    epic_key: str,
    packet_id: str,
    *,
    state: dict | None = None,
) -> PacketPlanReviewStateSnapshot:
    root = repo_root(root)
    artifacts = packet_plan_artifacts(root, epic_key, packet_id)
    payload = state or resolve_packet_plan_review_state(root, epic_key, packet_id) or {}

    def resolve_optional_path(value: object) -> Path | None:
        if isinstance(value, str) and value:
            return Path(value)
        return None

    status = str(payload.get("status") or "proposal_submitted")
    if status not in PACKET_PLAN_REVIEW_STATUSES:
        status = "proposal_submitted"

    return PacketPlanReviewStateSnapshot(
        status=status,
        current_artifact=resolve_optional_path(payload.get("current_artifact")),
        submitted_artifact=resolve_optional_path(payload.get("submitted_artifact")),
        proposal_artifact=artifacts.proposal_md,
        review_artifact=artifacts.review_md,
        response_artifact=artifacts.response_md,
        implementation_plan_artifact=artifacts.implementation_plan_md,
        accepted_artifact=resolve_optional_path(payload.get("accepted_artifact")),
    )


def packet_plan_expected_artifact_path(
    root: Path,
    epic_key: str,
    packet_id: str,
    *,
    state: dict | None = None,
) -> Path | None:
    snapshot = packet_plan_review_state_snapshot(
        root,
        epic_key,
        packet_id,
        state=state,
    )
    return snapshot.expected_artifact


def packet_plan_requires_revision_run(
    root: Path,
    epic_key: str,
    packet_id: str,
    *,
    state: dict | None = None,
) -> bool:
    snapshot = packet_plan_review_state_snapshot(
        root,
        epic_key,
        packet_id,
        state=state,
    )
    return snapshot.requires_revision_run


def packet_plan_monitor_state(
    root: Path,
    epic_key: str,
    packet_id: str,
    *,
    state: dict | None = None,
) -> dict[str, object]:
    snapshot = packet_plan_review_state_snapshot(
        root,
        epic_key,
        packet_id,
        state=state,
    )
    expected = snapshot.expected_artifact
    return {
        "status": snapshot.status,
        "waitable": snapshot.status in PACKET_PLAN_WAITABLE_STATUSES,
        "requires_revision_run": snapshot.requires_revision_run,
        "accepted": snapshot.accepted,
        "current_artifact": str(snapshot.current_artifact) if snapshot.current_artifact else None,
        "submitted_artifact": str(snapshot.submitted_artifact) if snapshot.submitted_artifact else None,
        "expected_artifact": str(expected) if expected else None,
        "accepted_artifact": str(snapshot.accepted_artifact) if snapshot.accepted_artifact else None,
        "implementation_plan_artifact": str(snapshot.implementation_plan_artifact),
    }


def packet_plan_requires_acceptance(root: Path, epic_key: str, packet_id: str) -> bool:
    root = repo_root(root)
    state = resolve_packet_plan_review_state(root, epic_key, packet_id)
    if state is not None:
        return True
    proposal = packet_plan_proposal_artifact_path(root, epic_key, packet_id)
    review = packet_plan_review_artifact_path(root, epic_key, packet_id)
    response = packet_plan_response_artifact_path(root, epic_key, packet_id)
    return any(path.exists() for path in (proposal, review, response))


def implementation_review_monitor_state(
    root: Path,
    epic_key: str,
    group_id: str,
    packet_id: str | None,
    *,
    status: str | None = None,
    completion_state: str | None = None,
    worker: dict | None = None,
    last_action: str | None = None,
) -> dict[str, object]:
    implementation_plan = (
        resolve_approved_plan_path(root, epic_key, packet_id, None) if packet_id else None
    )
    result_artifact = run_artifact_path(root, epic_key, group_id, "result")
    worker_payload = worker if isinstance(worker, dict) else {}
    worker_status = worker_payload.get("status")
    worker_note = worker_payload.get("note")
    review_ready = bool(
        status == "pending_review"
        or worker_status == "pending_review"
        or last_action == "worker_marked_pending_review"
    )

    if review_ready:
        snapshot = ImplementationReviewMonitorSnapshot(
            status="pending_review",
            completion_state="in_progress",
            review_ready=True,
            waitable=False,
            next_action="review_result",
            implementation_plan_artifact=implementation_plan,
            result_artifact=result_artifact,
            worker_status=worker_status if isinstance(worker_status, str) else None,
            worker_note=worker_note if isinstance(worker_note, str) else None,
        )
    elif completion_state in {"failed", "timed_out"}:
        snapshot = ImplementationReviewMonitorSnapshot(
            status=status or str(completion_state),
            completion_state=completion_state,
            review_ready=False,
            waitable=False,
            next_action="inspect_failure",
            implementation_plan_artifact=implementation_plan,
            result_artifact=result_artifact,
            worker_status=worker_status if isinstance(worker_status, str) else None,
            worker_note=worker_note if isinstance(worker_note, str) else None,
        )
    elif completion_state == "completed":
        snapshot = ImplementationReviewMonitorSnapshot(
            status="completed_without_review_signal",
            completion_state="completed",
            review_ready=False,
            waitable=False,
            next_action="inspect_completion",
            implementation_plan_artifact=implementation_plan,
            result_artifact=result_artifact,
            worker_status=worker_status if isinstance(worker_status, str) else None,
            worker_note=worker_note if isinstance(worker_note, str) else None,
        )
    else:
        current_status = status or "unknown"
        waitable = current_status in {"prepared", "launched", "running", "steered"}
        snapshot = ImplementationReviewMonitorSnapshot(
            status=current_status,
            completion_state=completion_state,
            review_ready=False,
            waitable=waitable,
            next_action="wait_for_worker" if waitable else "inspect_run_state",
            implementation_plan_artifact=implementation_plan,
            result_artifact=result_artifact,
            worker_status=worker_status if isinstance(worker_status, str) else None,
            worker_note=worker_note if isinstance(worker_note, str) else None,
        )

    return {
        "status": snapshot.status,
        "completion_state": snapshot.completion_state,
        "review_ready": snapshot.review_ready,
        "waitable": snapshot.waitable,
        "next_action": snapshot.next_action,
        "implementation_plan_artifact": (
            str(snapshot.implementation_plan_artifact) if snapshot.implementation_plan_artifact else None
        ),
        "result_artifact": str(snapshot.result_artifact) if snapshot.result_artifact else None,
        "worker_status": snapshot.worker_status,
        "worker_note": snapshot.worker_note,
    }


def initialize_packet_plan_review_state(root: Path, epic_key: str, packet_id: str) -> Path:
    root = repo_root(root)
    artifacts = packet_plan_artifacts(root, epic_key, packet_id)
    proposal = artifacts.proposal_md
    state_path = artifacts.review_state_json
    payload = packet_plan_review_state_template(
        root,
        epic_key,
        packet_id,
        status="proposal_submitted",
        proposal_path=proposal,
    )
    payload["current_artifact"] = str(proposal.resolve())
    payload["submitted_artifact"] = str(proposal.resolve())
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state_path


def resolve_approved_plan_path(
    root: Path,
    epic_key: str,
    packet_id: str | None,
    approved_plan_arg: str | None,
) -> Path | None:
    if approved_plan_arg:
        return Path(approved_plan_arg).resolve()
    if packet_id:
        state = resolve_packet_plan_review_state(root, epic_key, packet_id)
        if state is not None:
            if state.get("status") != "accepted":
                return None
            accepted = state.get("implementation_plan_artifact")
            if isinstance(accepted, str) and accepted:
                candidate = Path(accepted)
                if candidate.exists():
                    return candidate
        candidate = implementation_plan_artifact_path(root, epic_key, packet_id)
        if candidate.exists():
            return candidate
        legacy = legacy_opencode_plan_artifact_path(root, epic_key, packet_id)
        if legacy.exists():
            return legacy
    return None


def build_launch_prompt(
    handoff: dict,
    handoff_path: Path,
    root: Path,
    *,
    phase: str = "implementing",
    approved_plan_path: Path | None = None,
) -> str:
    root = repo_root(root)
    repo_name = root.name
    validation_command = full_suite_command(root)
    secondary = ", ".join(handoff.get("secondary_issues", [])) or "none"
    pending_review_command = render_implement_command(
        root,
        "pending-review",
        handoff["epic_key"],
        handoff["group_id"],
        "--repo-root",
        ".",
        python_executable="python3",
    )
    if phase == "planning":
        return f"""Read and follow AGENTS.md and CONTRIBUTING.md before making changes.

Then read the epic slice handoff at {handoff_path.relative_to(root)}.

This is a plan-first run. Do not edit files, create branches, or make any code changes yet.

Your task for this session is only to:
- inspect the handoff and relevant repo surfaces
- produce a concrete implementation plan for {handoff['primary_issue']} and {', '.join(handoff.get('secondary_issues', [])) or 'the scoped slice'}
- identify the exact files, interfaces, tests, and validation steps you expect to touch
- call out any ambiguity, boundary risk, or handoff weakness before implementation starts

Execution rules:
- Treat the handoff input as the source of truth for scope, branch naming, traceability, implementation steps, validation steps, risks, and exit criteria.
- Work only on the primary and secondary Jira issues listed in the handoff.
- Do not widen scope beyond the handoff.
- If the handoff is ambiguous or incomplete, stop and report the ambiguity instead of inventing requirements.
- Prefer the repo's documented full validation command where applicable ({validation_command}).
- Do not start implementation in this run.
- Do not edit any files in this run.
- Do not switch branches in this run.

At the end, provide only:
- implementation plan
- expected files/packages to change
- expected tests/validation
- open questions or blockers
"""

    plan_clause = ""
    plan_rules = ""
    if approved_plan_path:
        relative_plan = approved_plan_path.relative_to(root)
        plan_clause = f"\nThen read the approved plan at {relative_plan}.\n"
        if approved_plan_path.name.endswith(".implementation-plan.md") or approved_plan_path.name.endswith(".opencode-plan.md"):
            plan_rules = f"""
- You previously generated an initial draft plan for this packet.
- {relative_plan} is the reviewer-accepted implementation brief for this packet.
- Treat {relative_plan} as superseding your original draft plan.
- The handoff remains authoritative for scope, constraints, validation expectations, and Jira traceability.
- The reviewed implementation brief is authoritative for concrete implementation approach.
- Do not replace the reviewed implementation brief with a new plan unless you find a real conflict in the repo.
- If the reviewed implementation brief contains a seam assumption that the repo contradicts, stop and report the conflict instead of improvising.
- If the handoff and reviewed implementation brief conflict, stop and report the conflict instead of choosing one silently.
"""
        else:
            plan_rules = """
- Treat the approved plan markdown as the authoritative implementation plan when it is provided.
- If the handoff and approved plan conflict, stop and report the conflict instead of choosing one silently.
"""

    return f"""Read and follow AGENTS.md and CONTRIBUTING.md before making changes.

Then read the epic slice handoff at {handoff_path.relative_to(root)}.{plan_clause}
This is an implementation-only run starting from an already approved plan. Implement only that slice in this repository.

Repository:
- {repo_name}

Authoritative execution inputs:
- Primary Jira key: {handoff['primary_issue']}
- Secondary Jira keys: {secondary}
- Branch name: {handoff['branch_name']}
- Goal: {handoff['goal']}
{f"- Packet type: {handoff.get('packet_type')}" if handoff.get('packet_type') else ""}
{f"- Risk class: {handoff.get('risk_class')}" if handoff.get('risk_class') else ""}
{f"- Recommended executor: {handoff.get('recommended_executor')}" if handoff.get('recommended_executor') else ""}

Execution rules:
- Treat the handoff input as the source of truth for scope, branch naming, traceability, implementation steps, validation steps, risks, and exit criteria.
- Work only on the primary and secondary Jira issues listed in the handoff.
- Work on the current branch only.
- Do not create a new branch in this run.
- Do not switch branches in this run.
- Follow the repository guidance in AGENTS.md and CONTRIBUTING.md, including commit message format and PR traceability expectations.
- Do not widen scope beyond the handoff.
- If the handoff is ambiguous or incomplete, stop and report the ambiguity instead of inventing behavior.
- Prefer the repo's documented full validation command where applicable ({validation_command}).
{chr(10).join(f"- Routing note: {item}" for item in handoff.get("routing_notes", []))}
{plan_rules.rstrip()}

Before editing:
- Read the handoff.
- Read the reviewed plan when one is provided.
- Create a short todo list limited to tasks that are inside the packet scope and reviewed plan.
- If you believe you need a todo item outside the packet scope, stop and report instead of expanding the task.
- Start with the listed implementation files and only search beyond them if you hit a concrete repo question.

Implementation steps:
{chr(10).join(f"- {step}" for step in handoff.get("implementation_steps", []))}

Validation steps:
{chr(10).join(f"- {step}" for step in handoff.get("validation_steps", []))}

At the end, summarize:
- files changed
- key implementation decisions
- validation run
- any remaining risks or blockers

If you believe the implementation pass is complete and ready for human review, as your final step run:
- {pending_review_command}

Use that only to mark worker state as pending review.
Do not mark the packet completed in metadata; reviewer acceptance is separate.
"""


def build_steer_prompt(handoff: dict, handoff_path: Path, root: Path, steering_message: str) -> str:
    root = repo_root(root)
    return f"""Continue the existing implementation session for {handoff['group_id']} using the same handoff at {handoff_path.relative_to(root)}.

Before proceeding:
- Re-read AGENTS.md and CONTRIBUTING.md if needed for branch, commit, validation, or PR traceability rules.
- Stay strictly within the handoff scope.

Steering update:
{steering_message}

If this steering conflicts with the handoff, stop and report the conflict instead of guessing.
"""
