#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.markdown import bullet_values, parse_markdown_sections, single_bullet
from pm_dawn_core.profile import (
    load_project_profile as load_core_project_profile,
    make_default_profile,
    repo_root,
)
from pm_dawn_core.runtime import run_cmd

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

DEFAULT_PROJECT_PROFILE: dict = make_default_profile()


@dataclass(frozen=True)
class JiraPrPaths:
    root: Path
    epic_root: Path
    slice_md: Path
    plan_md: Path
    packets_dir: Path
    run_json: Path
    run_result_md: Path
    pr_dir: Path
    handoffs_dir: Path


def emit_json(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def load_project_profile(root: Path) -> dict:
    return load_core_project_profile(root, DEFAULT_PROJECT_PROFILE)


def issue_key_re(profile: dict) -> re.Pattern[str]:
    return re.compile(str(profile.get("project", {}).get("issue_key_pattern", r"\b[A-Z][A-Z0-9]+-\d+\b")))


def full_suite_command(profile: dict) -> str:
    return str(profile.get("validation", {}).get("full_suite_command", "make check"))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def jira_pr_paths(root: Path, epic_key: str, group_id: str) -> JiraPrPaths:
    epic_root = root / ".pm-dawn" / "epics" / epic_key
    return JiraPrPaths(
        root=root,
        epic_root=epic_root,
        slice_md=epic_root / "slices" / f"{group_id}.md",
        plan_md=epic_root / "plans" / f"{group_id}.plan.md",
        packets_dir=epic_root / "packets",
        run_json=epic_root / "ops" / "runs" / f"{group_id}.json",
        run_result_md=epic_root / "ops" / "runs" / f"{group_id}.result.md",
        pr_dir=epic_root / "ops" / "pr",
        handoffs_dir=epic_root / "ops" / "handoffs",
    )


def validate_handoff(data: dict) -> None:
    missing = [field for field in REQUIRED_HANDOFF_FIELDS if field not in data]
    if missing:
        raise RuntimeError(f"slice Markdown missing required fields: {', '.join(missing)}")


def normalize_none_list(values: list[str]) -> list[str]:
    return [] if values == ["None"] else values


def normalize_branch_candidates(branch_name: str, profile: dict) -> set[str]:
    candidates = {branch_name}
    if profile.get("branches", {}).get("allow_codex_prefix", True):
        if branch_name.startswith("codex/"):
            candidates.add(branch_name.removeprefix("codex/"))
        else:
            candidates.add(f"codex/{branch_name}")
    return candidates


def parse_packet_markdown(path: Path) -> dict:
    title, sections = parse_markdown_sections(read_text(path))
    primary_issue = ""
    secondary_issues: list[str] = []
    for item in bullet_values(sections.get("Jira Traceability", [])):
        if item.startswith("Primary:"):
            primary_issue = item.split(":", 1)[1].strip()
        elif item.startswith("Additional:"):
            extra = item.split(":", 1)[1].strip()
            if extra and extra != "None":
                secondary_issues = [part.strip() for part in extra.split(",") if part.strip()]
    packet_type = ""
    for item in bullet_values(sections.get("Why This Packet Is Isolated", [])):
        if item.lower().startswith("packet type:"):
            packet_type = item.split(":", 1)[1].strip().lower()
            break
    return {
        "title": title,
        "packet_id": single_bullet(sections.get("Packet ID", [])),
        "goal": single_bullet(sections.get("Goal", [])),
        "packet_type": packet_type,
        "depends_on": [] if bullet_values(sections.get("Depends On", [])) == ["None"] else bullet_values(sections.get("Depends On", [])),
        "files_to_read": [] if bullet_values(sections.get("Files to Read", [])) == ["None"] else bullet_values(sections.get("Files to Read", [])),
        "files_to_change": [] if bullet_values(sections.get("Files to Change", [])) == ["None"] else bullet_values(sections.get("Files to Change", [])),
        "implementation_steps": [] if bullet_values(sections.get("Implementation Steps", [])) == ["None"] else bullet_values(sections.get("Implementation Steps", [])),
        "validation_steps": [] if bullet_values(sections.get("Validation Steps", [])) == ["None"] else bullet_values(sections.get("Validation Steps", [])),
        "acceptance_checks": [] if bullet_values(sections.get("Acceptance Checks", [])) == ["None"] else bullet_values(sections.get("Acceptance Checks", [])),
        "constraints": [] if bullet_values(sections.get("Constraints", [])) == ["None"] else bullet_values(sections.get("Constraints", [])),
        "open_questions": [] if bullet_values(sections.get("Open Questions", [])) == ["None"] else bullet_values(sections.get("Open Questions", [])),
        "branch_name": single_bullet(sections.get("Branch Recommendation", [])),
        "commit_scope_guidance": single_bullet(sections.get("Commit Scope Guidance", [])),
        "primary_issue": primary_issue,
        "secondary_issues": secondary_issues,
    }


def parse_section_body(markdown: str, section_name: str) -> list[str]:
    _title, sections = parse_markdown_sections(markdown)
    values = bullet_values(sections.get(section_name, []))
    return [] if values == ["None"] else values


def current_branch(root: Path) -> str:
    return run_cmd(["git", "branch", "--show-current"], cwd=root).stdout.strip()


def base_ref(root: Path) -> str:
    origin_main = subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=root, capture_output=True, text=True, check=False)
    return "origin/main" if origin_main.returncode == 0 else "main"


def branch_commit_subjects(root: Path, base: str) -> list[str]:
    proc = run_cmd(["git", "log", "--format=%s", f"{base}..HEAD"], cwd=root)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def jira_keys_in_text(text: str, profile: dict) -> list[str]:
    return sorted(dict.fromkeys(issue_key_re(profile).findall(text)))


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


def short_goal(goal: str, limit: int = 72) -> str:
    clean = goal.strip().rstrip(".")
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def canonical_title(source: dict) -> str:
    return f"{source['primary_issue']}: {short_goal(source['goal'], 70)}"


def canonical_body(source: dict, validation_lines: list[str]) -> str:
    change_lines = source.get("what_changed", []) or [source["goal"]]
    additional = ", ".join(source.get("secondary_issues", [])) or "None"
    lines = [
        "What changed",
        *[f"- {item}" for item in change_lines],
        "",
        "Jira",
        f"- Primary: {source['primary_issue']}",
        f"- Additional: {additional}",
        "",
        "Validation",
        *[f"- {item}" for item in validation_lines],
    ]
    follow_up = source.get("follow_up", [])
    if follow_up:
        lines += ["", "Follow-up", *[f"- {item}" for item in follow_up]]
    return "\n".join(lines) + "\n"


def pr_sections(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if line in {"What changed", "Jira", "Validation", "Follow-up"}:
            current = line
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def parse_validation_lines_from_markdown(path: Path) -> list[str]:
    if not path.exists():
        return []
    return parse_section_body(read_text(path), "Validation")


def parse_validation_lines_from_body(body: str) -> list[str]:
    return [line[2:].strip() for line in pr_sections(body).get("Validation", []) if line.strip().startswith("- ")]


def collect_validation_lines(
    root: Path,
    source: dict,
    *,
    explicit_lines: list[str] | None = None,
    validation_file: Path | None = None,
    existing_pr: dict | None = None,
) -> tuple[list[str], str | None]:
    if explicit_lines:
        return [line for line in explicit_lines if line.strip()], "explicit_lines"
    if validation_file:
        lines = [line.strip()[2:].strip() if line.strip().startswith("- ") else line.strip() for line in read_text(validation_file).splitlines() if line.strip()]
        return lines, str(validation_file)
    result_md = source.get("run_result_md")
    if result_md:
        lines = parse_validation_lines_from_markdown(Path(result_md))
        if lines:
            return lines, str(result_md)
    if existing_pr:
        lines = parse_validation_lines_from_body(existing_pr.get("body", ""))
        if lines:
            return lines, f"pr:{existing_pr['number']}"
    return [], None


def artifact_stem(group_id: str, packet_id: str | None = None) -> str:
    return packet_id or group_id


def pr_artifact_paths(root: Path, epic_key: str, group_id: str, packet_id: str | None = None) -> tuple[Path, Path, Path]:
    stem = artifact_stem(group_id, packet_id)
    pr_dir = jira_pr_paths(root, epic_key, group_id).pr_dir
    return (
        pr_dir / f"{stem}.title.txt",
        pr_dir / f"{stem}.body.md",
        pr_dir / f"{stem}.verify.json",
    )


def compile_packet(root: Path, epic_key: str, group_id: str, packet_id: str) -> tuple[dict, Path]:
    output_path = jira_pr_paths(root, epic_key, group_id).handoffs_dir / f"{packet_id}.json"
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


def parse_slice_markdown(path: Path) -> dict:
    title, sections = parse_markdown_sections(read_text(path))
    markdown = read_text(path)
    inline_values: dict[str, str] = {}
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        for prefix in ("Group ID:", "Primary Jira Key:", "Secondary Jira Keys:"):
            if line.startswith(prefix):
                inline_values[prefix[:-1]] = line.split(":", 1)[1].strip()
    primary_issue = inline_values.get("Primary Jira Key", single_bullet(sections.get("Primary Jira Key", [])))
    secondary = inline_values.get("Secondary Jira Keys", single_bullet(sections.get("Secondary Jira Keys", []), "None"))
    secondary_issues = [] if secondary == "None" else [part.strip() for part in secondary.split(",") if part.strip()]
    pr_primary = primary_issue
    pr_additional = list(secondary_issues)
    for item in bullet_values(sections.get("PR Traceability", [])):
        if item.startswith("Primary:"):
            pr_primary = item.split(":", 1)[1].strip()
        elif item.startswith("Additional:"):
            extra = item.split(":", 1)[1].strip()
            pr_additional = [] if extra == "None" else [part.strip() for part in extra.split(",") if part.strip()]
    return {
        "title": title,
        "schema_version": "v1",
        "epic_key": path.parent.parent.name,
        "group_id": inline_values.get("Group ID", path.stem),
        "primary_issue": primary_issue,
        "secondary_issues": secondary_issues,
        "goal": single_bullet(sections.get("Goal", [])),
        "branch_name": single_bullet(sections.get("Branch Recommendation", [])),
        "pr_traceability": {
            "primary_issue": pr_primary or primary_issue,
            "additional_issues": pr_additional,
        },
        "entry_criteria": normalize_none_list(bullet_values(sections.get("Entry Criteria", []))),
        "exit_criteria": normalize_none_list(bullet_values(sections.get("Exit Criteria", []))),
        "repo_surfaces": normalize_none_list(bullet_values(sections.get("Repo Surfaces", []))),
        "implementation_steps": parse_section_body(markdown, "Implementation Steps"),
        "validation_steps": parse_section_body(markdown, "Validation Steps"),
        "risks": normalize_none_list(bullet_values(sections.get("Risks and Constraints", []))),
        "open_questions": parse_section_body(markdown, "Open Questions"),
        "source_context": {},
    }


def parse_plan_markdown(path: Path) -> dict:
    markdown = read_text(path)
    title, sections = parse_markdown_sections(markdown)
    packet_breakdown = parse_section_body(markdown, "Packet Breakdown")
    return {
        "title": title,
        "goal": single_bullet(sections.get("Goal", [])),
        "files_likely_to_change": parse_section_body(markdown, "Files Likely to Change"),
        "packet_breakdown": packet_breakdown,
    }


def load_pr_source(root: Path, epic_key: str, group_id: str, packet_id: str | None = None) -> dict:
    paths = jira_pr_paths(root, epic_key, group_id)
    if not paths.slice_md.exists():
        raise RuntimeError(f"slice Markdown not found: {paths.slice_md}")
    handoff = parse_slice_markdown(paths.slice_md)
    validate_handoff(handoff)
    slice_md = handoff
    plan_md = parse_plan_markdown(paths.plan_md) if paths.plan_md.exists() else {}
    current = current_branch(root)
    if packet_id:
        packet_md = paths.packets_dir / f"{packet_id}.md"
        if not packet_md.exists():
            raise RuntimeError(f"packet Markdown not found: {packet_md}")
        packet = parse_packet_markdown(packet_md)
        compiled, compiled_path = compile_packet(root, epic_key, group_id, packet_id)
        source = {
            "source_kind": "packet",
            "source_path": str(packet_md),
            "compiled_json": str(compiled_path),
            "epic_key": epic_key,
            "group_id": group_id,
            "packet_id": packet_id,
            "primary_issue": compiled["primary_issue"],
            "secondary_issues": compiled.get("secondary_issues", []),
            "branch_name": compiled["branch_name"],
            "goal": compiled["goal"],
            "pr_traceability": compiled["pr_traceability"],
            "commit_scope_guidance": compiled["source_context"].get("commit_scope_guidance", packet.get("commit_scope_guidance", "")),
            "what_changed": packet.get("implementation_steps") or [packet["goal"]],
            "run_result_md": None,
        }
    else:
        source_kind = "plan" if paths.plan_md.exists() else "slice"
        what_changed = (
            plan_md.get("packet_breakdown")
            or slice_md.get("implementation_steps")
            or handoff.get("implementation_steps", [])
            or [plan_md.get("goal") or slice_md.get("goal") or handoff["goal"]]
        )
        source_path = str(paths.plan_md) if paths.plan_md.exists() else (
            str(paths.slice_md)
        )
        source = {
            "source_kind": source_kind,
            "source_path": source_path,
            "compiled_json": None,
            "epic_key": epic_key,
            "group_id": group_id,
            "packet_id": None,
            "primary_issue": slice_md.get("primary_issue") or handoff["primary_issue"],
            "secondary_issues": slice_md.get("secondary_issues") or handoff.get("secondary_issues", []),
            "branch_name": slice_md.get("branch_name") or handoff["branch_name"],
            "goal": plan_md.get("goal") or slice_md.get("goal") or handoff["goal"],
            "pr_traceability": handoff["pr_traceability"],
            "commit_scope_guidance": "",
            "what_changed": what_changed,
            "run_result_md": None,
        }
    if paths.run_json.exists():
        run_meta = read_json(paths.run_json)
        result_md = run_meta.get("artifacts", {}).get("result_md")
        if result_md:
            source["run_result_md"] = result_md
    source["current_branch"] = current
    source["title"] = canonical_title(source)
    title_path, body_path, verify_path = pr_artifact_paths(root, epic_key, group_id, packet_id)
    source["title_path"] = str(title_path)
    source["body_path"] = str(body_path)
    source["verify_path"] = str(verify_path)
    return source


def inspect_branch_traceability(root: Path, source: dict, profile: dict) -> dict:
    branch = current_branch(root)
    base = base_ref(root)
    subjects = branch_commit_subjects(root, base)
    subject_keys = [jira_keys_in_text(subject, profile) for subject in subjects]
    flat_keys = sorted(dict.fromkeys(key for keys in subject_keys for key in keys))
    primary = source["primary_issue"]
    secondary = set(source.get("secondary_issues", []))
    warnings: list[str] = []
    blocking_errors: list[str] = []
    expected_candidates = normalize_branch_candidates(source["branch_name"], profile)
    if branch not in expected_candidates:
        blocking_errors.append(f"current branch {branch} does not match expected branch {source['branch_name']}")
    if not any(primary in keys for keys in subject_keys):
        blocking_errors.append(f"no branch commit references the primary Jira key {primary}")
    extra_keys = [key for key in flat_keys if key not in {primary, *secondary}]
    if extra_keys:
        warnings.append(f"commit history references Jira keys outside the source set: {', '.join(extra_keys)}")
    if secondary and not any(any(key in secondary for key in keys) for keys in subject_keys):
        warnings.append("grouped work is represented, but no commit message references a secondary Jira key")
    return {
        "current_branch": branch,
        "expected_branch": source["branch_name"],
        "expected_branch_candidates": sorted(expected_candidates),
        "base_ref": base,
        "commit_subjects": subjects,
        "commit_keys": flat_keys,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
    }


def verify_live_pr(source: dict, pr: dict, expected_title: str, profile: dict) -> tuple[list[str], list[str]]:
    blocking_errors: list[str] = []
    warnings: list[str] = []
    body = pr.get("body", "")
    sections = pr_sections(body)
    jira_lines = [line[2:].strip() for line in sections.get("Jira", []) if line.strip().startswith("- ")]
    validation_lines = [line[2:].strip() for line in sections.get("Validation", []) if line.strip().startswith("- ")]
    if "Jira" not in sections:
        blocking_errors.append("live PR body is missing the Jira section")
    required_keys = [source["primary_issue"], *source.get("secondary_issues", [])]
    for key in required_keys:
        if key not in body:
            blocking_errors.append(f"live PR body is missing Jira key {key}")
    if not any(line.startswith("Primary:") for line in jira_lines):
        blocking_errors.append("live PR Jira section is missing the Primary line")
    if not any(line.startswith("Additional:") for line in jira_lines):
        blocking_errors.append("live PR Jira section is missing the Additional line")
    if "Validation" not in sections or not validation_lines:
        blocking_errors.append("live PR body is missing a non-empty Validation section")
    if pr.get("title") != expected_title:
        warnings.append("live PR title differs from the canonical generated title")
    validation_command = full_suite_command(profile)
    if not any(validation_command.lower() in line.lower() for line in validation_lines):
        warnings.append(f"validation is narrower than {validation_command}")
    return blocking_errors, warnings
