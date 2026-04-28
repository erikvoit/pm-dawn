from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .artifacts import normalize_none_list, read_json, read_text
from .layout import compiled_packet_json_path, epic_root, pr_root, run_metadata_path, run_artifact_path, slice_plan_path
from .markdown import (
    bullet_values,
    parse_markdown_sections,
    parse_packet_markdown,
    parse_plan_markdown,
    parse_slice_markdown,
    single_bullet,
)


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


def issue_key_re(profile: dict) -> re.Pattern[str]:
    pattern = str(profile.get("project", {}).get("issue_key_pattern", r"\b[A-Z][A-Z0-9]+-\d+\b"))
    return re.compile(pattern)


def jira_keys_in_text(text: str, profile: dict) -> list[str]:
    return sorted(dict.fromkeys(issue_key_re(profile).findall(text)))


def normalize_branch_candidates(branch_name: str, profile: dict) -> set[str]:
    candidates = {branch_name}
    if profile.get("branches", {}).get("allow_codex_prefix", True):
        if branch_name.startswith("codex/"):
            candidates.add(branch_name.removeprefix("codex/"))
        else:
            candidates.add(f"codex/{branch_name}")
    return candidates


def full_suite_command(profile: dict) -> str:
    return str(profile.get("validation", {}).get("full_suite_command", "make check"))


def jira_pr_paths(root: Path, epic_key: str, group_id: str) -> JiraPrPaths:
    root = Path(root).resolve()
    root_epic = epic_root(root, epic_key)
    return JiraPrPaths(
        root=root,
        epic_root=root_epic,
        slice_md=root_epic / "slices" / f"{group_id}.md",
        plan_md=slice_plan_path(root, epic_key, group_id),
        packets_dir=root_epic / "packets",
        run_json=run_metadata_path(root, epic_key, group_id),
        run_result_md=run_artifact_path(root, epic_key, group_id, "result"),
        pr_dir=pr_root(root, epic_key),
        handoffs_dir=root_epic / "ops" / "handoffs",
    )


def validate_handoff(data: dict) -> None:
    missing = [field for field in REQUIRED_HANDOFF_FIELDS if field not in data]
    if missing:
        raise RuntimeError(f"slice Markdown missing required fields: {', '.join(missing)}")


def parse_section_body(markdown: str, section_name: str) -> list[str]:
    _title, sections = parse_markdown_sections(markdown)
    values = bullet_values(sections.get(section_name, []))
    return normalize_none_list(values)


def pr_plan_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    markdown = read_text(path)
    parsed = parse_plan_markdown(path)
    return {
        "title": parsed.get("title"),
        "goal": parsed.get("goal", ""),
        "files_likely_to_change": parsed.get("files_to_change", []),
        "packet_breakdown": parse_section_body(markdown, "Packet Breakdown"),
    }


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
        lines = [
            line.strip()[2:].strip() if line.strip().startswith("- ") else line.strip()
            for line in read_text(validation_file).splitlines()
            if line.strip()
        ]
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
    pr_dir = pr_root(root, epic_key)
    return (
        pr_dir / f"{stem}.title.txt",
        pr_dir / f"{stem}.body.md",
        pr_dir / f"{stem}.verify.json",
    )


def compiled_pr_packet_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return compiled_packet_json_path(root, epic_key, packet_id)


def build_pr_source(
    root: Path,
    epic_key: str,
    group_id: str,
    *,
    current_branch_name: str,
    packet_id: str | None = None,
    compiled_packet: dict | None = None,
    compiled_packet_path: Path | None = None,
) -> dict:
    paths = jira_pr_paths(root, epic_key, group_id)
    if not paths.slice_md.exists():
        raise RuntimeError(f"slice Markdown not found: {paths.slice_md}")
    handoff = parse_slice_markdown(paths.slice_md)
    validate_handoff(handoff)
    plan_md = pr_plan_summary(paths.plan_md)
    if packet_id:
        packet_md = paths.packets_dir / f"{packet_id}.md"
        if not packet_md.exists():
            raise RuntimeError(f"packet Markdown not found: {packet_md}")
        packet = parse_packet_markdown(packet_md)
        if compiled_packet is None:
            raise RuntimeError("compiled packet payload is required for packet PR source loading")
        source = {
            "source_kind": "packet",
            "source_path": str(packet_md),
            "compiled_json": str(compiled_packet_path) if compiled_packet_path else None,
            "epic_key": epic_key,
            "group_id": group_id,
            "packet_id": packet_id,
            "primary_issue": compiled_packet["primary_issue"],
            "secondary_issues": compiled_packet.get("secondary_issues", []),
            "branch_name": compiled_packet["branch_name"],
            "goal": compiled_packet["goal"],
            "pr_traceability": compiled_packet["pr_traceability"],
            "commit_scope_guidance": compiled_packet["source_context"].get(
                "commit_scope_guidance", packet.get("commit_scope_guidance", "")
            ),
            "what_changed": packet.get("implementation_steps") or [packet["goal"]],
            "run_result_md": None,
        }
    else:
        source_kind = "plan" if paths.plan_md.exists() else "slice"
        what_changed = (
            plan_md.get("packet_breakdown")
            or handoff.get("implementation_steps", [])
            or [plan_md.get("goal") or handoff["goal"]]
        )
        source = {
            "source_kind": source_kind,
            "source_path": str(paths.plan_md) if paths.plan_md.exists() else str(paths.slice_md),
            "compiled_json": None,
            "epic_key": epic_key,
            "group_id": group_id,
            "packet_id": None,
            "primary_issue": handoff["primary_issue"],
            "secondary_issues": handoff.get("secondary_issues", []),
            "branch_name": handoff["branch_name"],
            "goal": plan_md.get("goal") or handoff["goal"],
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
    source["current_branch"] = current_branch_name
    source["title"] = canonical_title(source)
    title_path, body_path, verify_path = pr_artifact_paths(root, epic_key, group_id, packet_id)
    source["title_path"] = str(title_path)
    source["body_path"] = str(body_path)
    source["verify_path"] = str(verify_path)
    return source


def inspect_branch_traceability_from_history(
    *,
    branch: str,
    base: str,
    subjects: list[str],
    source: dict,
    profile: dict,
) -> dict:
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
