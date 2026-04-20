#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    emit_json,
    explicit_paths_from_markdown,
    full_suite_command,
    keyword_tokens,
    load_handoff,
    load_project_profile,
    repo_root,
    search_candidates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an approved slice plan from a .pm-dawn handoff.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--inspect-json")
    return parser.parse_args()


def build_plan(root: Path, handoff: dict, markdown: str | None, inspect: dict, slice_md_path: str, inspect_json_path: str | None) -> dict:
    profile = load_project_profile(root)
    files_to_change = []
    for item in inspect.get("explicit_paths", []) + inspect.get("likely_files", []):
        if item not in files_to_change:
            files_to_change.append(item)

    if not files_to_change:
        files_to_change = handoff.get("repo_surfaces", [])

    files_not_to_change = list(inspect.get("files_not_to_change", []))
    approved_approach = [
        "Start from the existing slice handoff and current repo seams.",
        "Prefer narrow edits to the shared contract and immediate wiring surface before any broader refactor.",
        "Use packet-sized implementation units so execution can happen one approved packet at a time.",
    ]
    if markdown and "Do not redesign API routes" in markdown:
        approved_approach.append("Keep existing API route shapes stable unless a slice artifact explicitly requires a route-layer change.")

    validation_strategy = list(handoff.get("validation_steps", []))
    full_validation = full_suite_command(profile)
    if full_validation.lower() not in " ".join(validation_strategy).lower():
        validation_strategy.append(f"Run {full_validation} before PR review.")

    return {
        "schema_version": "v1",
        "epic_key": handoff["epic_key"],
        "group_id": handoff["group_id"],
        "primary_issue": handoff["primary_issue"],
        "secondary_issues": handoff.get("secondary_issues", []),
        "goal": handoff["goal"],
        "approved_approach": approved_approach,
        "files_to_change": files_to_change,
        "files_not_to_change": files_not_to_change,
        "validation_strategy": validation_strategy,
        "risks": handoff.get("risks", []),
        "open_questions": handoff.get("open_questions", []) + inspect.get("unresolved_ambiguity", []),
        "packets": [],
        "generated_from": {
            "slice_md": slice_md_path,
            "inspect_json": inspect_json_path,
        },
    }


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    handoff, paths = load_handoff(root, args.epic_key, args.group_id)
    markdown = paths.slice_md.read_text(encoding="utf-8")

    if args.inspect_json:
        import json

        inspect = json.loads(Path(args.inspect_json).read_text(encoding="utf-8"))
    else:
        explicit = explicit_paths_from_markdown(markdown, root)
        keywords = keyword_tokens(handoff, markdown)
        likely_files = search_candidates(root, handoff.get("repo_surfaces", []), keywords)
        for surface in handoff.get("repo_surfaces", []):
            if any(item == surface or item.startswith(f"{surface}/") for item in likely_files):
                continue
            likely_files.append(surface)
        inspect = {
            "explicit_paths": explicit,
            "keywords": keywords,
            "likely_files": likely_files,
            "files_not_to_change": [],
            "unresolved_ambiguity": [],
        }

    plan = build_plan(
        root,
        handoff,
        markdown,
        inspect,
        str(paths.slice_md),
        args.inspect_json,
    )
    emit_json(plan)


if __name__ == "__main__":
    main()
