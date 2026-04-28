#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.artifacts import (
    emit_json,
    list_lines,
    read_json,
    read_optional_text,
    write_json,
    write_text,
)
from pm_dawn_core.layout import SlicePaths, slice_paths
from pm_dawn_core.markdown import parse_slice_markdown
from pm_dawn_core.profile import (
    classify_path_fallback,
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


def load_project_profile(root: Path) -> dict:
    return load_core_project_profile(root, DEFAULT_PROJECT_PROFILE)


def validate_handoff(handoff: dict) -> None:
    missing = [field for field in REQUIRED_HANDOFF_FIELDS if field not in handoff]
    if missing:
        raise RuntimeError(f"slice handoff missing required fields: {', '.join(missing)}")


def load_handoff(root: Path, epic_key: str, group_id: str) -> tuple[dict, SlicePaths]:
    paths = slice_paths(root, epic_key, group_id)
    handoff = parse_slice_markdown(paths.slice_md)
    validate_handoff(handoff)
    return handoff, paths


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
