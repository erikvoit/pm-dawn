#!/usr/bin/env python3
"""Archive or delete a full .pm-dawn slice artifact family."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import emit_json
from pm_dawn_core.layout import epic_root, slice_archive_root, slice_artifact_targets
from pm_dawn_core.profile import repo_root


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
    epic_path = epic_root(root, args.epic_key)
    archive_path = slice_archive_root(root, args.epic_key, args.group_id)
    targets = slice_artifact_targets(root, args.epic_key, args.group_id)
    if not targets:
        raise SystemExit(f"no slice artifacts found for {args.epic_key}/{args.group_id}")

    archived: list[str] = []
    deleted: list[str] = []

    if args.mode == "archive":
        archived = _archive_targets(
            epic_root=epic_path,
            archive_root=archive_path,
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
