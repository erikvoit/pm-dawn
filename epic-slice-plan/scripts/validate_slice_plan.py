#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.layout import slice_paths
from pm_dawn_core.markdown import parse_packet_markdown, parse_plan_markdown

from common import emit_json, repo_root


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated slice plan and packet artifacts.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    paths = slice_paths(root, args.epic_key, args.group_id)
    plan_md = paths.plans_dir / f"{args.group_id}.plan.md"
    if not plan_md.exists():
        raise SystemExit(f"plan Markdown not found: {plan_md}")

    plan = parse_plan_markdown(plan_md)
    packet_paths = sorted(paths.packets_dir.glob(f"{args.group_id}__*.md"))
    packets = [parse_packet_markdown(path) for path in packet_paths]

    missing_plan = sorted(REQUIRED_PLAN_FIELDS - set(plan))
    if missing_plan:
        raise SystemExit(f"plan Markdown missing required fields: {', '.join(missing_plan)}")

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

    payload = {
        "epic_key": args.epic_key,
        "group_id": args.group_id,
        "ready": not errors,
        "packet_count": len(packets),
        "errors": errors,
    }
    emit_json(payload)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
