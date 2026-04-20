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
    read_text,
    repo_root,
    run_cmd,
    verify_live_pr,
    write_json,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare, verify, open, or sync a Jira-traceable PR.")
    parser.add_argument("mode", choices=("prepare", "verify", "open", "sync"))
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--validation-line", action="append", default=[])
    parser.add_argument("--validation-file")
    parser.add_argument("--base", default="main")
    parser.add_argument("--dry-run", action="store_true")
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
    title_path = repo_root(source["title_path"])
    body_path = repo_root(source["body_path"])
    verify_path = repo_root(source["verify_path"])
    write_text(title_path, source["title"] + "\n")
    write_text(body_path, body)

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

    if args.mode == "prepare":
        payload = {
            "mode": "prepare",
            "ready": not blocking_errors,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
            "title": source["title"],
            "title_path": str(title_path),
            "body_path": str(body_path),
            "validation_source": validation_source,
            "existing_pr": existing_pr,
        }
        write_json(verify_path, payload)
        emit_json(payload)
        if blocking_errors:
            raise SystemExit(1)
        return

    if args.mode == "verify":
        if not existing_pr:
            raise SystemExit("no live PR found for verification")
        live_errors, live_warnings = verify_live_pr(source, existing_pr, source["title"], profile)
        payload = {
            "mode": "verify",
            "ready": not (blocking_errors or live_errors),
            "blocking_errors": blocking_errors + live_errors,
            "warnings": warnings + live_warnings,
            "pr": existing_pr,
        }
        write_json(verify_path, payload)
        emit_json(payload)
        if payload["blocking_errors"]:
            raise SystemExit(1)
        return

    if blocking_errors:
        payload = {
            "mode": args.mode,
            "ready": False,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
            "existing_pr": existing_pr,
        }
        write_json(verify_path, payload)
        emit_json(payload)
        raise SystemExit(1)

    if args.mode == "open":
        if existing_pr:
            cmd = ["gh", "pr", "edit", str(existing_pr["number"]), "--title", read_text(title_path).strip(), "--body-file", str(body_path)]
            action = "update_existing"
            pr_number = existing_pr["number"]
        else:
            cmd = ["gh", "pr", "create", "--base", args.base, "--head", source["current_branch"], "--title", read_text(title_path).strip(), "--body-file", str(body_path)]
            action = "create"
            pr_number = None
        if not args.dry_run:
            run_cmd(cmd, cwd=root)
        pr = find_existing_pr(root, source["current_branch"], pr_number)
    else:  # sync
        if not existing_pr:
            raise SystemExit("no existing PR found to sync")
        cmd = ["gh", "pr", "edit", str(existing_pr["number"]), "--title", read_text(title_path).strip(), "--body-file", str(body_path)]
        action = "sync"
        if not args.dry_run:
            run_cmd(cmd, cwd=root)
        pr = find_existing_pr(root, source["current_branch"], existing_pr["number"])

    if args.dry_run and not (pr or existing_pr):
        live_errors = []
        live_warnings = []
    else:
        live_errors, live_warnings = verify_live_pr(source, pr or existing_pr, source["title"], profile)
    payload = {
        "mode": args.mode,
        "action": action,
        "dry_run": args.dry_run,
        "ready": not live_errors,
        "blocking_errors": live_errors,
        "warnings": warnings + live_warnings,
        "title_path": str(title_path),
        "body_path": str(body_path),
        "pr": pr or existing_pr,
        "command": cmd,
    }
    write_json(verify_path, payload)
    emit_json(payload)
    if live_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
