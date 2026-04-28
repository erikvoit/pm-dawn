from __future__ import annotations

import json
import sys
from pathlib import Path


def emit_json(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return read_text(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def normalize_none_list(values: list[str]) -> list[str]:
    return [] if values == ["None"] else values


def list_lines(items: list[str], default: str = "- None") -> str:
    if not items:
        return default
    return "\n".join(f"- {item}" for item in items)
