#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import (
    canonical_body,
    collect_validation_lines,
    emit_json,
    find_existing_pr,
    inspect_branch_traceability,
    load_project_profile,
    load_pr_source,
    repo_root,
    verify_live_pr,
    write_json,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PR readiness and Jira traceability for a .pm-dawn source.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--validation-line", action="append", default=[])
    parser.add_argument("--validation-file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    profile = load_project_profile(root)
    source = load_pr_source(root, args.epic_key, args.group_id, args.packet_id)
    branch = inspect_branch_traceability(root, source, profile)
    existing_pr = find_existing_pr(root, source["current_branch"], args.pr_number)
    validation_lines, validation_source = collect_validation_lines(
        root,
        source,
        explicit_lines=args.validation_line,
        validation_file=repo_root(args.validation_file) if args.validation_file else None,
        existing_pr=existing_pr,
    )
    body = canonical_body(source, validation_lines)
    write_text(repo_root(source["title_path"]), source["title"] + "\n")
    write_text(repo_root(source["body_path"]), body)

    blocking_errors = list(branch["blocking_errors"])
    warnings = list(branch["warnings"])
    if not validation_lines:
        blocking_errors.append("no validation lines were available from explicit input, a result artifact, or the existing PR")
    if "Jira\n" not in body:
        blocking_errors.append("generated PR body is missing the Jira section")
    for key in [source["primary_issue"], *source.get("secondary_issues", [])]:
        if key not in body:
            blocking_errors.append(f"generated PR body is missing Jira key {key}")
    validation_tail = body.split("Validation\n", 1)[1] if "Validation\n" in body else ""
    if "Validation\n" not in body or not any(line.strip().startswith("- ") for line in validation_tail.splitlines() if line.strip()):
        blocking_errors.append("generated PR body is missing a non-empty Validation section")
    validation_command = profile.get("validation", {}).get("full_suite_command", "make check")
    if not any(str(validation_command).lower() in line.lower() for line in validation_lines):
        warnings.append(f"validation is narrower than {validation_command}")

    live_pr_errors: list[str] = []
    live_pr_warnings: list[str] = []
    if existing_pr:
        live_pr_errors, live_pr_warnings = verify_live_pr(source, existing_pr, source["title"], profile)
        warnings.extend(live_pr_warnings)

    payload = {
        "epic_key": args.epic_key,
        "group_id": args.group_id,
        "packet_id": args.packet_id,
        "ready": not blocking_errors,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "validation_source": validation_source,
        "title": source["title"],
        "body_path": source["body_path"],
        "title_path": source["title_path"],
        "existing_pr": existing_pr,
        "live_pr_errors": live_pr_errors,
    }
    write_json(repo_root(source["verify_path"]), payload)
    emit_json(payload)
    if blocking_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
