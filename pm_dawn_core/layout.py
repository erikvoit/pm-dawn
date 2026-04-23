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


@dataclass(frozen=True)
class PacketPlanArtifacts:
    proposal_md: Path
    review_md: Path
    response_md: Path
    implementation_plan_md: Path
    review_state_json: Path


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
    return slice_paths(root, epic_key, group_id).slice_md


def slice_plan_path(root: Path, epic_key: str, group_id: str) -> Path:
    return slice_paths(root, epic_key, group_id).plans_dir / f"{group_id}.plan.md"


def packet_markdown_path(root: Path, epic_key: str, packet_id_value: str) -> Path:
    group_id = packet_id_value.split("__", 1)[0]
    return slice_paths(root, epic_key, group_id).packets_dir / f"{packet_id_value}.md"


def compiled_packet_json_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return handoffs_root(root, epic_key) / f"{packet_id}.json"


def implementation_plan_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return artifacts_root(root, epic_key) / f"{packet_id}.implementation-plan.md"


def packet_plan_proposal_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return artifacts_root(root, epic_key) / f"{packet_id}.plan-proposal.md"


def packet_plan_review_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return artifacts_root(root, epic_key) / f"{packet_id}.plan-review.md"


def packet_plan_response_artifact_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return artifacts_root(root, epic_key) / f"{packet_id}.plan-response.md"


def packet_plan_review_state_path(root: Path, epic_key: str, packet_id: str) -> Path:
    return artifacts_root(root, epic_key) / f"{packet_id}.plan-review.json"


def packet_plan_artifacts(root: Path, epic_key: str, packet_id: str) -> PacketPlanArtifacts:
    return PacketPlanArtifacts(
        proposal_md=packet_plan_proposal_artifact_path(root, epic_key, packet_id),
        review_md=packet_plan_review_artifact_path(root, epic_key, packet_id),
        response_md=packet_plan_response_artifact_path(root, epic_key, packet_id),
        implementation_plan_md=implementation_plan_artifact_path(root, epic_key, packet_id),
        review_state_json=packet_plan_review_state_path(root, epic_key, packet_id),
    )


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
        slice_plan_path(root, epic_key, group_id),
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
        f"ops/artifacts/{group_id}__*",
    ]
    for pattern in glob_patterns:
        targets.extend(path for path in epic_path.glob(pattern) if path.is_file())

    return sorted(set(targets))
