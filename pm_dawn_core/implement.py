from __future__ import annotations

import json
import sys
from pathlib import Path

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


DEFAULT_PROJECT_PROFILE: dict = make_default_profile(
    {
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


def slice_markdown_path(root: Path, epic_key: str, group_id: str) -> Path:
    return repo_root(root) / ".pm-dawn" / "epics" / epic_key / "slices" / f"{group_id}.md"


def packet_markdown_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return repo_root(root) / ".pm-dawn" / "epics" / epic_key / "packets" / f"{packet_id}.md"


def compiled_packet_json_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return repo_root(root) / ".pm-dawn" / "epics" / epic_key / "ops" / "handoffs" / f"{packet_id}.json"


def implementation_plan_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return repo_root(root) / ".pm-dawn" / "epics" / epic_key / "ops" / "artifacts" / f"{packet_id}.implementation-plan.md"


def legacy_opencode_plan_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return repo_root(root) / ".pm-dawn" / "epics" / epic_key / "ops" / "artifacts" / f"{packet_id}.opencode-plan.md"


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


def resolve_approved_plan_path(
    root: Path,
    epic_key: str,
    packet_id: str | None,
    approved_plan_arg: str | None,
) -> Path | None:
    if approved_plan_arg:
        return Path(approved_plan_arg).resolve()
    if packet_id:
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
    pending_review_script = (root / "epic-slice-implement" / "scripts" / "mark_slice_pending_review.py").relative_to(root)
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
- {relative_plan} is the reviewed and corrected implementation brief for this packet.
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
- python3 "{pending_review_script}" {handoff['epic_key']} {handoff['group_id']} --repo-root .

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
