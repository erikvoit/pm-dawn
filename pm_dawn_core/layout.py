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


def archive_root(root: Path) -> Path:
    return pm_dawn_root(root) / "archive"


def epic_archive_root(root: Path, epic_key: str) -> Path:
    return archive_root(root) / epic_key


def slice_archive_root(root: Path, epic_key: str, group_id: str) -> Path:
    return epic_archive_root(root, epic_key) / group_id


def handoffs_root(root: Path, epic_key: str) -> Path:
    return ops_root(root, epic_key) / "handoffs"


def artifacts_root(root: Path, epic_key: str) -> Path:
    return ops_root(root, epic_key) / "artifacts"


def runs_root(root: Path, epic_key: str) -> Path:
    return ops_root(root, epic_key) / "runs"


def pr_root(root: Path, epic_key: str) -> Path:
    return ops_root(root, epic_key) / "pr"


def slice_markdown_path(root: Path, epic_key: str, group_id: str) -> Path:
    return epic_root(root, epic_key) / "slices" / f"{group_id}.md"


def packet_markdown_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return epic_root(root, epic_key) / "packets" / f"{packet_id}.md"


def compiled_packet_json_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return handoffs_root(root, epic_key) / f"{packet_id}.json"


def implementation_plan_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return artifacts_root(root, epic_key) / f"{packet_id}.implementation-plan.md"


def legacy_opencode_plan_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return artifacts_root(root, epic_key) / f"{packet_id}.opencode-plan.md"


def reviewed_plan_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    preferred = implementation_plan_artifact_path(root, epic_key, packet_id)
    if preferred.exists():
        return preferred
    return legacy_opencode_plan_artifact_path(root, epic_key, packet_id)


def run_metadata_path(root: Path, epic_key: str, group_id: str) -> Path:
    return runs_root(root, epic_key) / f"{group_id}.json"


def run_artifact_path(root: Path, epic_key: str, group_id: str, kind: str) -> Path:
    return runs_root(root, epic_key) / f"{group_id}.{kind}.md"


def slice_artifact_targets(root: Path, epic_key: str, group_id: str) -> list[Path]:
    epic_path = epic_root(root, epic_key)
    targets: list[Path] = []
    exact = [
        slice_markdown_path(root, epic_key, group_id),
        epic_path / "plans" / f"{group_id}.plan.md",
        run_metadata_path(root, epic_key, group_id),
        run_artifact_path(root, epic_key, group_id, "plan"),
        run_artifact_path(root, epic_key, group_id, "result"),
        pr_root(root, epic_key) / f"{group_id}.title.txt",
        pr_root(root, epic_key) / f"{group_id}.body.md",
        pr_root(root, epic_key) / f"{group_id}.verify.json",
    ]
    targets.extend(path for path in exact if path.exists())

    glob_patterns = [
        f"packets/{group_id}__*.md",
        f"ops/handoffs/{group_id}__*.json",
        f"ops/pr/{group_id}__*.title.txt",
        f"ops/pr/{group_id}__*.body.md",
        f"ops/pr/{group_id}__*.verify.json",
        f"ops/artifacts/*{group_id}*",
    ]
    for pattern in glob_patterns:
        targets.extend(path for path in epic_path.glob(pattern) if path.is_file())

    return sorted(set(targets))
