#!/usr/bin/env python3
"""Archive or delete a full .pm-dawn slice artifact family."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import emit_json, repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive or delete .pm-dawn slice artifacts.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--mode",
        choices=("archive", "delete"),
        required=True,
        help="Archive merged slice artifacts or delete them once Jira is updated.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be archived or deleted without modifying files.",
    )
    return parser.parse_args()


def _iter_targets(epic_root: Path, group_id: str) -> list[Path]:
    targets: list[Path] = []
    exact = [
        epic_root / "slices" / f"{group_id}.md",
        epic_root / "plans" / f"{group_id}.plan.md",
        epic_root / "ops" / "runs" / f"{group_id}.json",
        epic_root / "ops" / "runs" / f"{group_id}.plan.md",
        epic_root / "ops" / "runs" / f"{group_id}.result.md",
        epic_root / "ops" / "pr" / f"{group_id}.title.txt",
        epic_root / "ops" / "pr" / f"{group_id}.body.md",
        epic_root / "ops" / "pr" / f"{group_id}.verify.json",
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
        targets.extend(path for path in epic_root.glob(pattern) if path.is_file())

    # Stable order and dedupe.
    return sorted(set(targets))


def _archive_targets(
    *,
    epic_root: Path,
    archive_root: Path,
    targets: list[Path],
    dry_run: bool,
) -> list[str]:
    archived: list[str] = []
    for path in targets:
        destination = archive_root / path.relative_to(epic_root)
        archived.append(str(destination))
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(destination))
    return archived


def _delete_targets(*, targets: list[Path], dry_run: bool) -> list[str]:
    deleted: list[str] = []
    for path in targets:
        deleted.append(str(path))
        if dry_run:
            continue
        path.unlink()
    return deleted


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    epic_root = root / ".pm-dawn" / "epics" / args.epic_key
    archive_root = root / ".pm-dawn" / "archive" / args.epic_key / args.group_id
    targets = _iter_targets(epic_root, args.group_id)
    if not targets:
        raise SystemExit(f"no slice artifacts found for {args.epic_key}/{args.group_id}")

    archived: list[str] = []
    deleted: list[str] = []

    if args.mode == "archive":
        archived = _archive_targets(
            epic_root=epic_root,
            archive_root=archive_root,
            targets=targets,
            dry_run=args.dry_run,
        )
    else:
        deleted = _delete_targets(targets=targets, dry_run=args.dry_run)

    emit_json(
        {
            "epic_key": args.epic_key,
            "group_id": args.group_id,
            "mode": args.mode,
            "dry_run": args.dry_run,
            "target_count": len(targets),
            "targets": [str(path) for path in targets],
            "archived": archived,
            "deleted": deleted,
        }
    )


if __name__ == "__main__":
    main()
