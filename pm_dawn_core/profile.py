from __future__ import annotations

import copy
import json
from pathlib import Path
import tomllib


BASE_PROJECT_PROFILE: dict = {
    "project": {
        "name": "PM Dawn Project",
        "issue_key_pattern": r"\b[A-Z][A-Z0-9]+-\d+\b",
    },
    "branches": {
        "allowed_prefixes": ["feature", "fix", "chore"],
        "template": "<type>/<jira-key>-<slug>",
        "allow_codex_prefix": True,
    },
    "validation": {
        "full_suite_command": "make check",
    },
}


def clone_profile(profile: dict) -> dict:
    return copy.deepcopy(profile)


def repo_root(path: str | Path = ".") -> Path:
    return Path(path).resolve()


def project_profile_path(root: Path) -> Path:
    return repo_root(root) / ".pm-dawn" / "project-profile.toml"


def merge_profile(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_profile(merged[key], value)
        else:
            merged[key] = value
    return merged


def make_default_profile(overrides: dict | None = None) -> dict:
    profile = clone_profile(BASE_PROJECT_PROFILE)
    if overrides:
        profile = merge_profile(profile, overrides)
    return profile


def load_project_profile(root: Path, default_profile: dict | None = None) -> dict:
    default_payload = clone_profile(default_profile or BASE_PROJECT_PROFILE)
    path = project_profile_path(root)
    if not path.exists():
        return default_payload
    loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    return merge_profile(default_payload, loaded)


def classify_path_fallback(path: str) -> str:
    lower = path.lower()
    basename = Path(lower).name
    suffix = Path(lower).suffix

    if lower.startswith("tests/") or "/tests/" in lower or basename.startswith("test_"):
        return "tests"
    if basename in {"common.py", "profile.py", "layout.py", "markdown.py", "bootstrap.py", "implement.py"}:
        return "contract"
    if any(token in basename for token in ("schema", "protocol", "contract")):
        return "contract"
    if basename in {"readme.md", "skill.md"} or "/references/" in lower or suffix == ".md":
        return "cleanup"
    if "/scripts/" in lower or suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs"}:
        return "wiring"
    return "cleanup"
