#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.layout import SlicePaths, packet_markdown_path, slice_paths
from pm_dawn_core.markdown import (
    bullet_values,
    parse_markdown_sections,
    parse_packet_markdown,
    parse_plan_markdown,
    single_bullet,
)
from pm_dawn_core.profile import (
    classify_path_fallback,
    load_project_profile as load_core_project_profile,
    make_default_profile,
    repo_root,
)

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

DEFAULT_PROJECT_PROFILE: dict = make_default_profile(
    {
        "planning": {
            "default_search_surfaces": ["."],
            "secondary_search_surfaces": ["tests"],
            "include_tests_by_default": False,
            "prefer_non_test_matches": True,
        },
        "packetization": {
            "allow_tests_only_feature_slices": False,
            "feature_goal_keywords": [
                "add",
                "build",
                "wire",
                "implement",
                "support",
                "introduce",
                "surface",
                "panel",
                "screen",
                "view",
                "hydrate",
                "hydration",
                "reconnect",
                "diagnostic",
                "lane",
                "control",
                "stream",
                "replay",
                "policy",
                "simulate",
                "bootstrap",
                "profile",
                "repository",
            ],
            "wiring_step_keywords": [
                "wire",
                "wiring",
                "client",
                "panel",
                "screen",
                "view",
                "attach",
                "detach",
                "stream",
                "replay",
                "hydrate",
                "resume",
                "render",
                "control",
                "load",
                "fetch",
                "bootstrap",
            ],
            "behavioral_tokens": [
                "workflow",
                "attach",
                "detach",
                "session",
                "stream",
                "replay",
                "auth",
                "policy",
                "lane",
                "control",
                "navigation",
                "bootstrap",
                "profile",
            ],
        },
        "review": {
            "tag_surfaces": {},
        },
        "seam_rules": [
            {"prefix": "tests/", "packet_type": "tests", "search_weight": 1},
        ],
    }
)


def emit_json(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def load_project_profile(root: Path) -> dict:
    return load_core_project_profile(root, DEFAULT_PROJECT_PROFILE)
def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def validate_handoff(handoff: dict) -> None:
    missing = [field for field in REQUIRED_HANDOFF_FIELDS if field not in handoff]
    if missing:
        raise RuntimeError(f"slice handoff missing required fields: {', '.join(missing)}")


def parse_slice_markdown(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"slice Markdown not found: {path}")
    markdown = path.read_text(encoding="utf-8")
    _title, sections = parse_markdown_sections(markdown)
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
    source_context = {
        "epic_review_date": "unknown-date",
        "implementation_group_reason": "",
    }
    for item in bullet_values(sections.get("Source Review Context", [])):
        if item.startswith("Derived from epic review of "):
            tail = item.split(" on ", 1)
            if len(tail) == 2:
                source_context["epic_review_date"] = tail[1].rstrip(".")
        else:
            source_context["implementation_group_reason"] = item
    return {
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
        "entry_criteria": [] if bullet_values(sections.get("Entry Criteria", [])) == ["None"] else bullet_values(sections.get("Entry Criteria", [])),
        "exit_criteria": [] if bullet_values(sections.get("Exit Criteria", [])) == ["None"] else bullet_values(sections.get("Exit Criteria", [])),
        "repo_surfaces": [] if bullet_values(sections.get("Repo Surfaces", [])) == ["None"] else bullet_values(sections.get("Repo Surfaces", [])),
        "implementation_steps": [] if bullet_values(sections.get("Implementation Steps", [])) == ["None"] else bullet_values(sections.get("Implementation Steps", [])),
        "validation_steps": [] if bullet_values(sections.get("Validation Steps", [])) == ["None"] else bullet_values(sections.get("Validation Steps", [])),
        "risks": [] if bullet_values(sections.get("Risks and Constraints", [])) == ["None"] else bullet_values(sections.get("Risks and Constraints", [])),
        "open_questions": [] if bullet_values(sections.get("Open Questions", [])) == ["None"] else bullet_values(sections.get("Open Questions", [])),
        "source_context": source_context,
    }


def load_handoff(root: Path, epic_key: str, group_id: str) -> tuple[dict, SlicePaths]:
    paths = slice_paths(root, epic_key, group_id)
    handoff = parse_slice_markdown(paths.slice_md)
    validate_handoff(handoff)
    return handoff, paths


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"command failed: {' '.join(cmd)}")
    return proc


def tracked_files(root: Path, prefix: str) -> list[str]:
    if prefix in {"", "."}:
        proc = run_cmd(["rg", "--files", "."], cwd=root)
        return [line.strip().removeprefix("./") for line in proc.stdout.splitlines() if line.strip()]
    target = root / prefix
    if target.is_file():
        return [str(target.relative_to(root))]
    if target.is_dir():
        proc = run_cmd(["rg", "--files", str(target)], cwd=root)
        return [str(Path(line).resolve().relative_to(root)) for line in proc.stdout.splitlines() if line.strip()]
    return []


def explicit_paths_from_markdown(markdown: str | None, root: Path) -> list[str]:
    if not markdown:
        return []
    matches = re.findall(r"`([^`]+)`", markdown)
    paths: list[str] = []
    for item in matches:
        candidate = (root / item).resolve()
        if candidate.exists() and candidate.is_file():
            paths.append(str(candidate.relative_to(root)))
    return sorted(dict.fromkeys(paths))


def keyword_tokens(handoff: dict, markdown: str | None) -> list[str]:
    text_parts = [
        handoff.get("goal", ""),
        " ".join(handoff.get("implementation_steps", [])),
        markdown or "",
    ]
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", " ".join(text_parts).lower())
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "plus",
        "only",
        "where",
        "when",
        "same",
        "ship",
        "should",
        "already",
        "present",
        "still",
        "sparse",
        "work",
        "slice",
        "story",
        "batch",
        "review",
        "pass",
        "backend",
        "existing",
        "cleanly",
        "single",
    }
    ordered = []
    for token in tokens:
        if len(token) < 4 or token in stopwords:
            continue
        if token not in ordered:
            ordered.append(token)
    return ordered[:16]


def search_candidates(root: Path, repo_surfaces: list[str], keywords: list[str]) -> list[str]:
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    profile = load_project_profile(root)
    planning = profile.get("planning", {})
    primary_surfaces = list(repo_surfaces)
    if not any(surface != "tests" for surface in primary_surfaces):
        primary_surfaces.extend(planning.get("default_search_surfaces", []))
    surfaces = list(
        dict.fromkeys(
            [
                *primary_surfaces,
                *(
                    planning.get("secondary_search_surfaces", [])
                    if planning.get("include_tests_by_default", False)
                    else []
                ),
            ]
        )
    )
    for surface in surfaces:
        for path in tracked_files(root, surface):
            if path in seen:
                continue
            lower = path.lower()
            basename = Path(lower).name
            matched = [keyword for keyword in keywords if keyword in lower]
            if not matched:
                continue
            score = len(matched)
            if any(keyword in basename for keyword in matched):
                score += 2
            rule = seam_rule_for_path(path, profile)
            score += int(rule.get("search_weight", 0))
            if basename.startswith("test_") and not planning.get("prefer_non_test_matches", True):
                score += 1
            if planning.get("prefer_non_test_matches", True) and classify_repo_path(path, profile) == "tests":
                score -= 2
            scored.append((score, path))
            seen.add(path)
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [path for _score, path in scored[:12]]


def seam_rule_for_path(path: str, profile: dict) -> dict:
    best: dict | None = None
    for rule in profile.get("seam_rules", []):
        prefix = rule.get("prefix", "")
        normalized = prefix.rstrip("/")
        if prefix and (path.startswith(prefix) or path == normalized):
            if best is None or len(prefix) > len(best.get("prefix", "")):
                best = rule
    return best or {}


def classify_repo_path(path: str, profile: dict) -> str:
    rule = seam_rule_for_path(path, profile)
    if rule:
        return str(rule.get("packet_type", "cleanup"))
    return classify_path_fallback(path)


def full_suite_command(profile: dict) -> str:
    return str(profile.get("validation", {}).get("full_suite_command", "make check"))


def feature_slice_requires_non_test_packet(handoff: dict, plan: dict, profile: dict) -> bool:
    packetization = profile.get("packetization", {})
    if packetization.get("allow_tests_only_feature_slices", False):
        return False
    text = " ".join(
        [
            handoff.get("goal", ""),
            " ".join(handoff.get("implementation_steps", [])),
            " ".join(plan.get("files_to_change", [])),
        ]
    ).lower()
    keywords = [str(item).lower() for item in packetization.get("feature_goal_keywords", [])]
    if any(keyword in text for keyword in keywords):
        return True
    return any(not str(path).startswith("tests/") for path in handoff.get("repo_surfaces", []))


def packet_id(group_id: str, packet_type: str, index: int) -> str:
    return f"{group_id}__{index:02d}_{packet_type}"


def list_lines(items: list[str], default: str = "- None") -> str:
    if not items:
        return default
    return "\n".join(f"- {item}" for item in items)
