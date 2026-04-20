from __future__ import annotations

from pathlib import Path

from .profile import repo_root


def pm_dawn_root(root: Path) -> Path:
    return repo_root(root) / ".pm-dawn"


def epics_root(root: Path) -> Path:
    return pm_dawn_root(root) / "epics"


def epic_root(root: Path, epic_key: str) -> Path:
    return epics_root(root) / epic_key


def ops_root(root: Path, epic_key: str) -> Path:
    return epic_root(root, epic_key) / "ops"


def project_profile_path(root: Path) -> Path:
    return pm_dawn_root(root) / "project-profile.toml"
