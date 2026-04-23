#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.profile import (
    load_project_profile as load_core_project_profile,
    make_default_profile,
    repo_root,
)
from pm_dawn_core.runtime import require_cli, run_cmd

def run_acli(args: list[str]) -> str:
    require_cli("acli")
    proc = run_cmd(["acli", *args], check=False)
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "unknown ACLI error"
        raise RuntimeError(message)
    return proc.stdout


def run_json(args: list[str]) -> object:
    output = run_acli(args)
    return json.loads(output)


def ensure_auth() -> None:
    try:
        run_acli(["jira", "auth", "status"])
    except RuntimeError as exc:
        raise RuntimeError(
            "ACLI is not authenticated. Run 'acli jira auth status' or the local Jira login helper first."
        ) from exc


def extract_adf_text(node: object) -> str:
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "hardBreak":
            return "\n"
        parts: list[str] = []
        if "text" in node and isinstance(node["text"], str):
            parts.append(node["text"])
        child_text = "".join(extract_adf_text(child) for child in node.get("content", []))
        if child_text:
            parts.append(child_text)
        text = "".join(parts)
        if node_type in {"paragraph", "heading", "bulletList", "orderedList", "listItem"} and text:
            if not text.endswith("\n"):
                text += "\n"
        return text
    if isinstance(node, list):
        text = "".join(extract_adf_text(item) for item in node)
        return text
    return ""


def issue_description(issue: dict) -> str:
    fields = issue.get("fields", {})
    desc = fields.get("description")
    if isinstance(desc, str):
        return desc
    return extract_adf_text(desc or "").strip()


def issue_parent_key(issue: dict) -> str | None:
    parent = issue.get("fields", {}).get("parent")
    if isinstance(parent, dict):
        return parent.get("key")
    return None


def write_temp_file(content: str) -> Path:
    with NamedTemporaryFile("w", delete=False, suffix=".md", encoding="utf-8") as handle:
        handle.write(content)
        return Path(handle.name)


def emit_json(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def skill_tmp_dir() -> Path:
    path = skill_root() / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def skill_tmp_path(name: str) -> Path:
    return skill_tmp_dir() / name


def write_json_file(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit_json_and_write_tmp(payload: object, filename: str) -> None:
    write_json_file(skill_tmp_path(filename), payload)
    emit_json(payload)


def graph_epic_key(graph: dict) -> str | None:
    if isinstance(graph.get("epic_key"), str):
        return graph["epic_key"]
    epic = graph.get("epic")
    if isinstance(epic, dict):
        key = epic.get("key")
        if isinstance(key, str):
            return key
    return None


def require_matching_epic(expected_key: str, payload: dict, source: str) -> None:
    actual_key = graph_epic_key(payload) or payload.get("epic_key")
    if actual_key and actual_key != expected_key:
        raise RuntimeError(
            f"{source} belongs to `{actual_key}`, not `{expected_key}`. Refresh the Jira review artifacts before continuing."
        )


REQUIRED_STORY_SECTIONS = [
    "Context",
    "Scope",
    "Out of scope",
    "Acceptance criteria",
    "Test plan",
    "Dependencies",
]

DEFAULT_PROJECT_PROFILE: dict = make_default_profile(
    {
        "branches": {
            "default_type": "feature",
        },
        "review": {
            "tag_surfaces": {},
        },
    }
)


def load_project_profile(root: Path) -> dict:
    return load_core_project_profile(root, DEFAULT_PROJECT_PROFILE)


def parse_story_sections(description: str) -> dict[str, str]:
    text = description.strip()
    if not text:
        return {}
    headings = "|".join(re.escape(section) for section in REQUIRED_STORY_SECTIONS)
    pattern = re.compile(
        rf"(?im)^(?P<header>{headings}):\s*$"
        rf"|^(?P<header_inline>{headings}):\s*(?P<body_inline>.*)$"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return {}
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        header = match.group("header") or match.group("header_inline")
        start = match.end()
        if match.group("body_inline") is not None:
            body = match.group("body_inline").strip()
        else:
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
        sections[header] = body
    return sections


def story_quality(description: str) -> dict[str, object]:
    sections = parse_story_sections(description)
    missing_sections = [section for section in REQUIRED_STORY_SECTIONS if section not in sections]
    empty_sections = [section for section, body in sections.items() if not body.strip()]
    short_sections = [
        section
        for section, body in sections.items()
        if body.strip() and len(body.split()) < 5
    ]
    return {
        "sections": sections,
        "missing_sections": missing_sections,
        "empty_sections": empty_sections,
        "short_sections": short_sections,
        "is_normalized": not missing_sections and not empty_sections,
        "is_weak": bool(missing_sections or empty_sections or short_sections),
    }


def categorize_summary(summary: str) -> set[str]:
    s = summary.lower()

    def has_any_term(*terms: str) -> bool:
        return any(re.search(rf"\b{re.escape(term)}\b", s) for term in terms)

    tags: set[str] = set()
    if has_any_term("interface", "contract", "protocol", "abstraction"):
        tags.add("contract")
    if has_any_term("registry", "selection", "composition"):
        tags.add("registry")
    if has_any_term("adapter", "runtime"):
        tags.add("runtime")
    if has_any_term("approve", "interrupt", "resume", "control"):
        tags.add("control")
    if has_any_term("checkpoint", "replay", "debug"):
        tags.add("replay")
    if has_any_term("ui", "tui", "ux", "keyboard", "operator"):
        tags.add("ux")
    if has_any_term("hardening", "release", "safety", "timeout", "heartbeat"):
        tags.add("hardening")
    if has_any_term("lane", "scheduler", "admission"):
        tags.add("scheduler")
    if has_any_term("api", "endpoint", "stream"):
        tags.add("api")
    if has_any_term("scaffold", "proof", "proofing"):
        tags.add("scaffold")
    return tags
