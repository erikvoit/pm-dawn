from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .profile import repo_root


@dataclass(frozen=True)
class SlicePaths:
    root: Path
    epic_root: Path
    index_md: Path
    slice_md: Path
    ops_dir: Path
    plans_dir: Path
    packets_dir: Path
    handoffs_dir: Path
    artifacts_dir: Path


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


def slice_paths(root: Path, epic_key: str, group_id: str) -> SlicePaths:
    root_path = repo_root(root)
    epic_path = epic_root(root_path, epic_key)
    ops_path = epic_path / "ops"
    return SlicePaths(
        root=root_path,
        epic_root=epic_path,
        index_md=epic_path / "index.md",
        slice_md=epic_path / "slices" / f"{group_id}.md",
        ops_dir=ops_path,
        plans_dir=epic_path / "plans",
        packets_dir=epic_path / "packets",
        handoffs_dir=ops_path / "handoffs",
        artifacts_dir=ops_path / "artifacts",
    )


def packet_markdown_path(root: Path, epic_key: str, packet_id_value: str) -> Path:
    group_id = packet_id_value.split("__", 1)[0]
    return slice_paths(root, epic_key, group_id).packets_dir / f"{packet_id_value}.md"
