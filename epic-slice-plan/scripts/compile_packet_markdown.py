#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.layout import packet_markdown_path
from pm_dawn_core.markdown import parse_packet_markdown

from common import emit_json, load_handoff, repo_root, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile one packet Markdown artifact into execution JSON.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("packet_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output")
    return parser.parse_args()


def compile_packet(root: Path, epic_key: str, group_id: str, packet_id_value: str) -> tuple[dict, Path]:
    handoff, paths = load_handoff(root, epic_key, group_id)
    packet_path = packet_markdown_path(root, epic_key, packet_id_value)
    packet = parse_packet_markdown(packet_path)
    if packet["packet_id"] != packet_id_value:
        raise RuntimeError(f"packet Markdown id mismatch: expected {packet_id_value}, found {packet['packet_id']}")

    payload = {
        "schema_version": "v1",
        "epic_key": epic_key,
        "group_id": group_id,
        "packet_id": packet_id_value,
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
    output_path = paths.handoffs_dir / f"{packet_id_value}.json"
    return payload, output_path


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    payload, default_output = compile_packet(root, args.epic_key, args.group_id, args.packet_id)
    if args.output:
        output_path = Path(args.output).resolve()
        write_json(output_path, payload)
    else:
        write_json(default_output, payload)
    emit_json(payload)


if __name__ == "__main__":
    main()
