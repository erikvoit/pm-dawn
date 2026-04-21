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


def parse_packet_markdown(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"packet Markdown not found: {path}")
    markdown = path.read_text(encoding="utf-8")
    title, sections = parse_markdown_sections(markdown)
    packet_id_value = single_bullet(sections.get("Packet ID", []))
    packet_type = ""
    for item in bullet_values(sections.get("Why This Packet Is Isolated", [])):
        if item.lower().startswith("packet type:"):
            packet_type = item.split(":", 1)[1].strip().lower()
            break
    primary_issue = ""
    secondary_issues: list[str] = []
    for item in bullet_values(sections.get("Jira Traceability", [])):
        if item.startswith("Primary:"):
            primary_issue = item.split(":", 1)[1].strip()
        elif item.startswith("Additional:"):
            extra = item.split(":", 1)[1].strip()
            if extra and extra != "None":
                secondary_issues = [piece.strip() for piece in extra.split(",") if piece.strip()]
    branch_name = single_bullet(sections.get("Branch Recommendation", []))
    commit_scope_guidance = single_bullet(sections.get("Commit Scope Guidance", []))
    open_questions = bullet_values(sections.get("Open Questions", []))
    if open_questions == ["None"]:
        open_questions = []
    risk_class = ""
    recommended_executor = ""
    routing_notes: list[str] = []
    for item in bullet_values(sections.get("Execution Routing", [])):
        if item.startswith("Risk Class:"):
            risk_class = item.split(":", 1)[1].strip()
        elif item.startswith("Recommended Executor:"):
            recommended_executor = item.split(":", 1)[1].strip()
        else:
            routing_notes.append(item)
    return {
        "title": title,
        "packet_id": packet_id_value,
        "goal": single_bullet(sections.get("Goal", [])),
        "packet_type": packet_type,
        "depends_on": [] if bullet_values(sections.get("Depends On", [])) == ["None"] else bullet_values(sections.get("Depends On", [])),
        "files_to_read": [] if bullet_values(sections.get("Files to Read", [])) == ["None"] else bullet_values(sections.get("Files to Read", [])),
        "files_to_change": [] if bullet_values(sections.get("Files to Change", [])) == ["None"] else bullet_values(sections.get("Files to Change", [])),
        "implementation_steps": [] if bullet_values(sections.get("Implementation Steps", [])) == ["None"] else bullet_values(sections.get("Implementation Steps", [])),
        "validation_steps": [] if bullet_values(sections.get("Validation Steps", [])) == ["None"] else bullet_values(sections.get("Validation Steps", [])),
        "acceptance_checks": [] if bullet_values(sections.get("Acceptance Checks", [])) == ["None"] else bullet_values(sections.get("Acceptance Checks", [])),
        "constraints": [] if bullet_values(sections.get("Constraints", [])) == ["None"] else bullet_values(sections.get("Constraints", [])),
        "primary_issue": primary_issue,
        "secondary_issues": secondary_issues,
        "branch_name": branch_name,
        "commit_scope_guidance": commit_scope_guidance,
        "open_questions": open_questions,
        "risk_class": risk_class,
        "recommended_executor": recommended_executor,
        "routing_notes": routing_notes,
    }


def parse_plan_markdown(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"plan Markdown not found: {path}")
    markdown = path.read_text(encoding="utf-8")
    title, sections = parse_markdown_sections(markdown)
    packet_breakdown = bullet_values(sections.get("Packet Breakdown", []))
    packets: list[dict[str, str]] = []
    for item in packet_breakdown:
        packet_name, _sep, goal = item.partition(":")
        packets.append({"packet_id": packet_name.strip(), "goal": goal.strip()})
    packet_order = [] if bullet_values(sections.get("Packet Ordering", [])) == ["None"] else bullet_values(sections.get("Packet Ordering", []))
    return {
        "title": title,
        "slice_identity": bullet_values(sections.get("Slice Identity", [])),
        "goal": single_bullet(sections.get("Goal", [])),
        "approved_approach": [] if bullet_values(sections.get("Approved Implementation Approach", [])) == ["None"] else bullet_values(sections.get("Approved Implementation Approach", [])),
        "files_to_change": [] if bullet_values(sections.get("Files Likely to Change", [])) == ["None"] else bullet_values(sections.get("Files Likely to Change", [])),
        "files_not_to_change": [] if bullet_values(sections.get("Files Explicitly Not to Change", [])) == ["None"] else bullet_values(sections.get("Files Explicitly Not to Change", [])),
        "validation_strategy": [] if bullet_values(sections.get("Validation Strategy", [])) == ["None"] else bullet_values(sections.get("Validation Strategy", [])),
        "risks": [] if bullet_values(sections.get("Risks and Constraints", [])) == ["None"] else bullet_values(sections.get("Risks and Constraints", [])),
        "open_questions": [] if bullet_values(sections.get("Open Questions", [])) == ["None"] else bullet_values(sections.get("Open Questions", [])),
        "packets": packets,
        "packet_order": packet_order,
        "source_context": bullet_values(sections.get("Source Context", [])),
    }
