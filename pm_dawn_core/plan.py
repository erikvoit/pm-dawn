from __future__ import annotations

from pathlib import Path

from .implement import compile_packet_handoff as compile_implementation_packet_handoff
from .implement import load_handoff
from .layout import slice_paths
from .markdown import parse_packet_markdown, parse_plan_markdown


REQUIRED_PLAN_FIELDS = {
    "goal",
    "approved_approach",
    "files_to_change",
    "files_not_to_change",
    "validation_strategy",
    "risks",
    "open_questions",
    "packets",
    "packet_order",
    "source_context",
}

REQUIRED_PACKET_FIELDS = {
    "packet_id",
    "primary_issue",
    "secondary_issues",
    "packet_type",
    "risk_class",
    "recommended_executor",
    "routing_notes",
    "goal",
    "depends_on",
    "files_to_read",
    "files_to_change",
    "implementation_steps",
    "validation_steps",
    "acceptance_checks",
    "constraints",
    "open_questions",
    "branch_name",
    "commit_scope_guidance",
}


def compile_packet_handoff(root: Path, epic_key: str, group_id: str, packet_id: str) -> tuple[dict, Path]:
    return compile_implementation_packet_handoff(root, epic_key, group_id, packet_id)


def load_slice_handoff_payload(root: Path, epic_key: str, group_id: str) -> dict:
    handoff, paths = load_handoff(root, epic_key, group_id)
    return {
        "repo_root": str(Path(root).resolve()),
        "slice_markdown_path": str(paths),
        "handoff": handoff,
        "handoff_markdown_present": True,
        "handoff_markdown_preview": paths.read_text(encoding="utf-8")[:400],
    }


def validate_slice_plan_artifacts(root: Path, epic_key: str, group_id: str) -> dict:
    paths = slice_paths(root, epic_key, group_id)
    plan_md = paths.plans_dir / f"{group_id}.plan.md"
    if not plan_md.exists():
        raise RuntimeError(f"plan Markdown not found: {plan_md}")

    plan = parse_plan_markdown(plan_md)
    packet_paths = sorted(paths.packets_dir.glob(f"{group_id}__*.md"))
    packets = [parse_packet_markdown(path) for path in packet_paths]

    missing_plan = sorted(REQUIRED_PLAN_FIELDS - set(plan))
    if missing_plan:
        raise RuntimeError(f"plan Markdown missing required fields: {', '.join(missing_plan)}")

    packet_ids = {packet["packet_id"] for packet in packets}
    errors: list[str] = []
    if not packets:
        errors.append("no packet Markdown artifacts found")
    if not plan.get("files_to_change"):
        errors.append("plan Markdown has no Files Likely to Change entries")
    if plan.get("packet_order") and plan.get("packet_order") != [packet["packet_id"] for packet in packets]:
        errors.append("packet ordering in plan Markdown does not match the packet artifacts on disk")
    if [packet["packet_id"] for packet in plan.get("packets", [])] != [packet["packet_id"] for packet in packets]:
        errors.append("packet breakdown in plan Markdown does not match the packet artifacts on disk")
    if not plan.get("goal"):
        errors.append("plan Markdown has an empty Goal section")
    for packet in packets:
        missing = sorted(REQUIRED_PACKET_FIELDS - set(packet))
        if missing:
            errors.append(f"{packet.get('packet_id', '<unknown>')}: missing fields {', '.join(missing)}")
            continue
        for field in ("packet_id", "packet_type", "goal", "primary_issue", "branch_name", "commit_scope_guidance"):
            if not packet.get(field):
                errors.append(f"{packet['packet_id'] or '<unknown>'}: empty field {field}")
        for dep in packet.get("depends_on", []):
            if dep not in packet_ids:
                errors.append(f"{packet['packet_id']}: unknown dependency {dep}")
        if not (paths.packets_dir / f"{packet['packet_id']}.md").exists():
            errors.append(f"{packet['packet_id']}: missing packet Markdown artifact")

    return {
        "epic_key": epic_key,
        "group_id": group_id,
        "ready": not errors,
        "packet_count": len(packets),
        "errors": errors,
    }
