from __future__ import annotations

import re


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
