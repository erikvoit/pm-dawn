from __future__ import annotations

import re
from pathlib import Path


SECTION_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 /_-]+):\s*$")


def parse_markdown_sections(markdown: str) -> tuple[str | None, dict[str, list[str]]]:
    title: str | None = None
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            title = line[2:].strip()
            continue
        match = SECTION_RE.match(line)
        if match:
            current = match.group(1)
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return title, sections


def bullet_values(lines: list[str]) -> list[str]:
    values: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(stripped[2:].strip())
    return values


def single_bullet(lines: list[str], default: str = "") -> str:
    values = bullet_values(lines)
    return values[0] if values else default


def bullet_values_or_empty(lines: list[str]) -> list[str]:
    values = bullet_values(lines)
    return [] if values == ["None"] else values


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
        "entry_criteria": bullet_values_or_empty(sections.get("Entry Criteria", [])),
        "exit_criteria": bullet_values_or_empty(sections.get("Exit Criteria", [])),
        "repo_surfaces": bullet_values_or_empty(sections.get("Repo Surfaces", [])),
        "implementation_steps": bullet_values_or_empty(sections.get("Implementation Steps", [])),
        "validation_steps": bullet_values_or_empty(sections.get("Validation Steps", [])),
        "risks": bullet_values_or_empty(sections.get("Risks and Constraints", [])),
        "open_questions": bullet_values_or_empty(sections.get("Open Questions", [])),
        "source_context": source_context,
    }
