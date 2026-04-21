#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_execution_packets import build_packets
from build_slice_plan import build_plan
from common import (
    list_lines,
    load_handoff,
    load_project_profile,
    read_optional_text,
    repo_root,
    write_text,
)
from inspect_slice_context import build_inspect_payload
from pm_dawn_core.bootstrap import bootstrap_workspace


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate slice plan and packet artifacts under .pm-dawn.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--plan-json")
    parser.add_argument("--packets-json")
    return parser.parse_args()


def render_plan_md(epic_key: str, handoff: dict, plan: dict) -> str:
    return f"""# {epic_key} / {handoff['group_id']} / Slice Plan

Slice Identity:
- Group ID: {handoff['group_id']}
- Primary Jira Key: {handoff['primary_issue']}
- Secondary Jira Keys: {', '.join(handoff.get('secondary_issues', [])) or 'None'}

Goal:
{list_lines([plan['goal']])}

Approved Implementation Approach:
{list_lines(plan.get('approved_approach', []))}

Files Likely to Change:
{list_lines(plan.get('files_to_change', []))}

Files Explicitly Not to Change:
{list_lines(plan.get('files_not_to_change', []))}

Validation Strategy:
{list_lines(plan.get('validation_strategy', []))}

Risks and Constraints:
{list_lines(plan.get('risks', []))}

Open Questions:
{list_lines(plan.get('open_questions', []))}

Packet Breakdown:
{list_lines([f"{packet['packet_id']}: {packet['goal']}" for packet in plan.get('packets', [])])}

Packet Ordering:
{list_lines([packet['packet_id'] for packet in plan.get('packets', [])])}

Source Context:
- Slice Markdown: {plan.get('generated_from', {}).get('slice_md')}
- Inspect payload: {plan.get('generated_from', {}).get('inspect_json') or 'None'}
"""


def render_packet_md(packet: dict) -> str:
    isolated_reason = [
        f"Packet type: {packet['packet_type']}",
        "This packet is intentionally narrow and should not re-decide architecture.",
    ]
    return f"""# {packet['epic_key']} / {packet['packet_id']}

Packet ID:
- {packet['packet_id']}

Goal:
{list_lines([packet['goal']])}

Why This Packet Is Isolated:
{list_lines(isolated_reason)}

Depends On:
{list_lines(packet.get('depends_on', []))}

Files to Read:
{list_lines(packet.get('files_to_read', []))}

Files to Change:
{list_lines(packet.get('files_to_change', []))}

Implementation Steps:
{list_lines(packet.get('implementation_steps', []))}

Validation Steps:
{list_lines(packet.get('validation_steps', []))}

Acceptance Checks:
{list_lines(packet.get('acceptance_checks', []))}

Constraints:
{list_lines(packet.get('constraints', []))}

Open Questions:
{list_lines(packet.get('open_questions', []))}

Execution Routing:
- Risk Class: {packet['risk_class']}
- Recommended Executor: {packet['recommended_executor']}
{list_lines(packet.get('routing_notes', []))}

Branch Recommendation:
- {packet['branch_name']}

Commit Scope Guidance:
- {packet['commit_scope_guidance']}

Jira Traceability:
- Primary: {packet['primary_issue']}
- Additional: {', '.join(packet.get('secondary_issues', [])) or 'None'}
"""


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    bootstrap_workspace(root, create_profile=True)
    profile = load_project_profile(root)
    handoff, paths = load_handoff(root, args.epic_key, args.group_id)
    markdown = read_optional_text(paths.slice_md)

    if args.plan_json:
        plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    else:
        inspect_payload = build_inspect_payload(root, args.epic_key, args.group_id, handoff, markdown)
        plan = build_plan(
            root,
            handoff,
            markdown,
            inspect_payload,
            str(paths.slice_md),
            None,
        )

    if args.packets_json:
        packets_payload = json.loads(Path(args.packets_json).read_text(encoding="utf-8"))
    else:
        packets = build_packets(plan, handoff, profile)
        packets_payload = {
            "schema_version": "v1",
            "epic_key": args.epic_key,
            "group_id": args.group_id,
            "packet_count": len(packets),
            "packets": packets,
        }

    packets = packets_payload.get("packets", [])
    plan = {**plan, "packets": packets}

    plan_md_path = paths.plans_dir / f"{args.group_id}.plan.md"

    write_text(plan_md_path, render_plan_md(args.epic_key, handoff, plan))

    for stale_path in paths.packets_dir.glob(f"{args.group_id}__*.md"):
        stale_path.unlink()

    packet_files: list[str] = []
    for packet in packets:
        packet_md_path = paths.packets_dir / f"{packet['packet_id']}.md"
        write_text(packet_md_path, render_packet_md(packet))
        packet_files.append(str(packet_md_path))

    output = {
        "epic_key": args.epic_key,
        "group_id": args.group_id,
        "plan_md": str(plan_md_path),
        "packet_files": packet_files,
        "json_emitted": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
