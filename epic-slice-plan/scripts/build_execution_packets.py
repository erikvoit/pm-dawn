#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    classify_repo_path,
    emit_json,
    feature_slice_requires_non_test_packet,
    full_suite_command,
    load_handoff,
    load_project_profile,
    packet_id,
    parse_plan_markdown,
    repo_root,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split an approved slice plan into small execution packets.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--plan-json")
    return parser.parse_args()


def packet_goal(packet_type: str, handoff: dict) -> str:
    mapping = {
        "contract": "Land the smallest shared contract changes required by the slice.",
        "wiring": "Wire the approved contract into the immediate app/provider surfaces.",
        "tests": "Add or update focused tests for the approved contract and wiring behavior.",
        "cleanup": "Apply direct follow-up cleanup required by the preceding packets.",
    }
    return mapping[packet_type]


def top_level_areas(paths: list[str]) -> set[str]:
    areas: set[str] = set()
    for path in paths:
        if path.startswith("apps/"):
            parts = path.split("/", 2)
            areas.add("/".join(parts[:2]) if len(parts) >= 2 else "apps")
        elif path.startswith("packages/"):
            parts = path.split("/", 2)
            areas.add("/".join(parts[:2]) if len(parts) >= 2 else "packages")
        elif path.startswith("tests/"):
            areas.add("tests")
        else:
            areas.add(path.split("/", 1)[0])
    return areas


def classify_risk(packet_type: str, files_to_change: list[str], handoff: dict, profile: dict) -> tuple[str, str, list[str]]:
    lower_steps = " ".join(handoff.get("implementation_steps", [])).lower()
    areas = top_level_areas(files_to_change)

    if packet_type == "tests":
        return (
            "mechanical",
            "local_small_model",
            [
                "This packet is test-focused and should be straightforward to validate with narrow checks.",
                "Wrong changes are likely to be caught quickly by the targeted test loop.",
            ],
        )

    behavioral_tokens = tuple(profile.get("packetization", {}).get("behavioral_tokens", []))
    if packet_type == "contract" and len(areas - {"tests"}) > 1:
        return (
            "architectural",
            "direct_or_strong_model",
            [
                "This packet changes contract-level behavior across more than one package boundary.",
                "Small-model improvisation here is likely to create cross-seam drift.",
            ],
        )
    if packet_type == "wiring" and (
        len(areas - {"tests"}) > 1 or any(token in lower_steps for token in behavioral_tokens)
    ):
        return (
            "behavioral",
            "direct_or_strong_model",
            [
                "This packet depends on real product behavior across existing seams, not just mechanical edits.",
                "The implementer must represent missing backend capability honestly instead of inventing it.",
            ],
        )
    if packet_type == "contract":
        return (
            "bounded",
            "local_small_model_with_review",
            [
                "The packet is small enough for local execution, but contract edits still need a strong review pass.",
            ],
        )
    if packet_type == "cleanup":
        return (
            "mechanical",
            "local_small_model",
            [
                "This packet is direct follow-up cleanup with narrow file scope.",
            ],
        )
    return (
        "bounded",
        "local_small_model_with_review",
        [
            "The packet is reasonably scoped, but it should be reviewed before acceptance.",
        ],
    )


def should_add_tests_packet(plan: dict, handoff: dict) -> bool:
    if plan.get("files_to_change") == ["tests/"]:
        return False

    non_test_files = [path for path in plan.get("files_to_change", []) if not path.startswith("tests/")]
    if not non_test_files:
        return False

    text = " ".join(
        [
            handoff.get("goal", ""),
            " ".join(handoff.get("implementation_steps", [])),
            " ".join(plan.get("validation_strategy", [])),
        ]
    ).lower()
    return any(token in text for token in ("test", "validate", "verification", "smoke"))


def build_packets(plan: dict, handoff: dict, profile: dict) -> list[dict]:
    grouped: dict[str, list[str]] = {"contract": [], "wiring": [], "tests": [], "cleanup": []}
    for path in plan.get("files_to_change", []):
        grouped[classify_repo_path(path, profile)].append(path)

    if not grouped["tests"] and should_add_tests_packet(plan, handoff):
        grouped["tests"] = ["tests/"]

    if (
        grouped["tests"]
        and not grouped["contract"]
        and not grouped["wiring"]
        and feature_slice_requires_non_test_packet(handoff, plan, profile)
    ):
        raise RuntimeError(
            "feature-oriented slice collapsed to tests-only packetization; unable to identify a non-test implementation seam"
        )

    ordered_types = [kind for kind in ("contract", "wiring", "tests", "cleanup") if grouped[kind]]
    packets: list[dict] = []
    previous_ids: list[str] = []
    index = 1
    full_validation = full_suite_command(profile)
    for kind in ordered_types:
        pid = packet_id(handoff["group_id"], kind, index)
        packet = {
            "schema_version": "v1",
            "packet_id": pid,
            "epic_key": handoff["epic_key"],
            "group_id": handoff["group_id"],
            "primary_issue": handoff["primary_issue"],
            "secondary_issues": handoff.get("secondary_issues", []),
            "packet_type": kind,
            "goal": packet_goal(kind, handoff),
            "depends_on": list(previous_ids),
            "files_to_read": list(dict.fromkeys(grouped[kind] + plan.get("files_not_to_change", [])))[:12],
            "files_to_change": grouped[kind],
            "implementation_steps": [
                step
                for step in handoff.get("implementation_steps", [])
                if (
                    (kind == "contract" and any(token in step.lower() for token in ("contract", "protocol", "type")))
                    or (kind == "wiring" and any(token in step.lower() for token in ("wire", "registry", "provider", "selection")))
                    or (kind == "tests" and any(token in step.lower() for token in ("test", "validate")))
                )
            ]
            or [packet_goal(kind, handoff)],
            "validation_steps": [
                step
                for step in plan.get("validation_strategy", [])
                if (kind == "tests" or full_validation.lower() not in step.lower() or kind in {"contract", "wiring"})
            ],
            "acceptance_checks": [
                f"{kind.capitalize()} packet changes are limited to the declared files.",
                "All packet validation steps pass.",
            ],
            "constraints": [
                "Do not widen scope beyond the approved slice plan.",
                "Do not redesign unrelated surfaces while executing this packet.",
            ],
            "open_questions": list(plan.get("open_questions", [])),
            "branch_name": handoff["branch_name"],
            "commit_scope_guidance": f"Use a commit focused on the {kind} packet and reference {handoff['primary_issue']}.",
        }
        risk_class, recommended_executor, routing_notes = classify_risk(kind, grouped[kind], handoff, profile)
        packet["risk_class"] = risk_class
        packet["recommended_executor"] = recommended_executor
        packet["routing_notes"] = routing_notes
        packets.append(packet)
        previous_ids.append(pid)
        index += 1
    return packets


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    profile = load_project_profile(root)
    handoff, paths = load_handoff(root, args.epic_key, args.group_id)
    if args.plan_json:
        plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    else:
        plan = parse_plan_markdown(paths.plans_dir / f"{args.group_id}.plan.md")
    packets = build_packets(plan, handoff, profile)
    emit_json(
        {
            "schema_version": "v1",
            "epic_key": args.epic_key,
            "group_id": args.group_id,
            "packet_count": len(packets),
            "packets": packets,
        }
    )


if __name__ == "__main__":
    main()
