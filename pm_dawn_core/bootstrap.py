from __future__ import annotations

from pathlib import Path

from .layout import pm_dawn_root, project_profile_path


def starter_project_profile() -> str:
    # TOML requires double-escaping: once for Python string, once for TOML regex
    # The issue_key_pattern must be a valid regex in the TOML file
    return """[project]
name = "PM Dawn Project"
issue_key_pattern = "\\\\b[A-Z][A-Z0-9]+-\\\\d+\\\\b"

[branches]
allowed_prefixes = ["feature", "fix", "chore"]
template = "<type>/<jira-key>-<slug>"
allow_codex_prefix = true

[validation]
full_suite_command = "make check"

[monitoring.defaults]
initial_session_check_seconds = 5
planning_artifact_grace_period_seconds = 60
implementation_artifact_grace_period_seconds = 120

[monitoring.pi]

[monitoring.opencode]

[planning]
default_search_surfaces = ["."]
secondary_search_surfaces = ["tests"]
include_tests_by_default = false
prefer_non_test_matches = true
"""


def bootstrap_workspace(root: Path, *, create_profile: bool = False) -> list[str]:
    pm_root = pm_dawn_root(root)
    created: list[str] = []
    for relative in ("epics", "archive", "tmp"):
        path = pm_root / relative
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(str(path))
    profile_path = project_profile_path(root)
    if create_profile and not profile_path.exists():
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(starter_project_profile(), encoding="utf-8")
        created.append(str(profile_path))
    return created
