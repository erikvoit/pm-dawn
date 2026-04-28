#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.artifacts import (
    emit_json,
    read_json,
    read_text,
    write_json,
    write_text,
)
from pm_dawn_core.profile import (
    load_project_profile as load_core_project_profile,
    make_default_profile,
    repo_root,
)
from pm_dawn_core.runtime import run_cmd
from pm_dawn_core.traceability import (
    JiraPrPaths,
    build_pr_source,
    canonical_body,
    canonical_title,
    collect_validation_lines,
    compiled_pr_packet_path,
    inspect_branch_traceability_from_history,
    jira_pr_paths,
    parse_packet_markdown,
    parse_section_body,
    pr_artifact_paths,
    pr_sections,
    short_goal,
    validate_handoff,
    verify_live_pr,
)

DEFAULT_PROJECT_PROFILE: dict = make_default_profile()


def load_project_profile(root: Path) -> dict:
    return load_core_project_profile(root, DEFAULT_PROJECT_PROFILE)


def full_suite_command(profile: dict) -> str:
    return str(profile.get("validation", {}).get("full_suite_command", "make check"))


def current_branch(root: Path) -> str:
    return run_cmd(["git", "branch", "--show-current"], cwd=root).stdout.strip()


def base_ref(root: Path) -> str:
    origin_main = subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=root, capture_output=True, text=True, check=False)
    return "origin/main" if origin_main.returncode == 0 else "main"


def branch_commit_subjects(root: Path, base: str) -> list[str]:
    proc = run_cmd(["git", "log", "--format=%s", f"{base}..HEAD"], cwd=root)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def find_existing_pr(root: Path, branch: str, pr_number: int | None = None) -> dict | None:
    if pr_number is not None:
        proc = run_cmd(
            ["gh", "pr", "view", str(pr_number), "--json", "number,title,body,url,headRefName,baseRefName"],
            cwd=root,
        )
        return json.loads(proc.stdout)
    try:
        proc = run_cmd(
            ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number,title,body,url,headRefName,baseRefName"],
            cwd=root,
        )
        data = json.loads(proc.stdout or "[]")
    except RuntimeError:
        data = []
    if data:
        return data[0]
    try:
        fallback = run_cmd(
            ["gh", "pr", "list", "--state", "open", "--json", "number,title,body,url,headRefName,baseRefName"],
            cwd=root,
        )
        all_open = json.loads(fallback.stdout or "[]")
    except RuntimeError:
        all_open = []
    for item in all_open:
        if item.get("headRefName") == branch:
            return item
    return None


def compile_packet(root: Path, epic_key: str, group_id: str, packet_id: str) -> tuple[dict, Path]:
    output_path = compiled_pr_packet_path(root, epic_key, packet_id)
    compile_script = Path(__file__).resolve().parents[2] / "epic-slice-plan" / "scripts" / "compile_packet_markdown.py"
    run_cmd(
        [
            sys.executable,
            str(compile_script),
            epic_key,
            group_id,
            packet_id,
            "--repo-root",
            str(root),
            "--output",
            str(output_path),
        ]
    )
    payload = read_json(output_path)
    return payload, output_path


def load_pr_source(root: Path, epic_key: str, group_id: str, packet_id: str | None = None) -> dict:
    current = current_branch(root)
    compiled = None
    compiled_path = None
    if packet_id:
        compiled, compiled_path = compile_packet(root, epic_key, group_id, packet_id)
    return build_pr_source(
        root,
        epic_key,
        group_id,
        current_branch_name=current,
        packet_id=packet_id,
        compiled_packet=compiled,
        compiled_packet_path=compiled_path,
    )


def inspect_branch_traceability(root: Path, source: dict, profile: dict) -> dict:
    branch = current_branch(root)
    base = base_ref(root)
    subjects = branch_commit_subjects(root, base)
    return inspect_branch_traceability_from_history(
        branch=branch,
        base=base,
        subjects=subjects,
        source=source,
        profile=profile,
    )
