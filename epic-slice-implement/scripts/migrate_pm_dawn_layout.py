#!/usr/bin/env python3
"""Migrate repo-local .pm-dawn data to the new epics/ + ops/ layout."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import emit_json, repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate .pm-dawn from handoffs/ to epics/ in one pass.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def move_file(src: Path, dest: Path, *, dry_run: bool, moved: list[dict]) -> None:
    if not src.exists():
        return
    moved.append({"from": str(src), "to": str(dest)})
    if dry_run:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))


def delete_file(path: Path, *, dry_run: bool, deleted: list[str]) -> None:
    if not path.exists():
        return
    deleted.append(str(path))
    if not dry_run:
        path.unlink()


def remove_empty_dirs(root: Path, *, dry_run: bool) -> None:
    if not root.exists():
        return
    for path in sorted((item for item in root.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
        if any(path.iterdir()):
            continue
        if not dry_run:
            path.rmdir()
    if root.exists() and not any(root.iterdir()) and not dry_run:
        root.rmdir()


def migrate_active_epics(pm_root: Path, *, dry_run: bool) -> tuple[list[dict], list[str]]:
    moved: list[dict] = []
    deleted: list[str] = []
    handoffs_root = pm_root / "handoffs"
    epics_root = pm_root / "epics"
    if not handoffs_root.exists():
        return moved, deleted

    for old_epic_root in sorted(path for path in handoffs_root.iterdir() if path.is_dir()):
        epic_key = old_epic_root.name
        new_epic_root = epics_root / epic_key
        move_file(old_epic_root / "index.md", new_epic_root / "index.md", dry_run=dry_run, moved=moved)
        delete_file(old_epic_root / "index.json", dry_run=dry_run, deleted=deleted)

        for path in sorted(old_epic_root.glob("*.md")):
            if path.name == "index.md":
                continue
            move_file(path, new_epic_root / "slices" / path.name, dry_run=dry_run, moved=moved)
        for path in sorted(old_epic_root.glob("*.json")):
            if path.name == "index.json":
                continue
            delete_file(path, dry_run=dry_run, deleted=deleted)

        for path in sorted((old_epic_root / "plans").glob("*.md")) if (old_epic_root / "plans").exists() else []:
            move_file(path, new_epic_root / "plans" / path.name, dry_run=dry_run, moved=moved)
        for path in sorted((old_epic_root / "plans").glob("*.json")) if (old_epic_root / "plans").exists() else []:
            delete_file(path, dry_run=dry_run, deleted=deleted)

        for path in sorted((old_epic_root / "packets").glob("*.md")) if (old_epic_root / "packets").exists() else []:
            move_file(path, new_epic_root / "packets" / path.name, dry_run=dry_run, moved=moved)
        for path in sorted((old_epic_root / "packets").glob("*.json")) if (old_epic_root / "packets").exists() else []:
            delete_file(path, dry_run=dry_run, deleted=deleted)
        compiled_dir = old_epic_root / "packets" / ".compiled"
        for path in sorted(compiled_dir.glob("*.json")) if compiled_dir.exists() else []:
            move_file(path, new_epic_root / "ops" / "handoffs" / path.name, dry_run=dry_run, moved=moved)

        for path in sorted((old_epic_root / "pr").glob("*")) if (old_epic_root / "pr").exists() else []:
            if path.is_file():
                move_file(path, new_epic_root / "ops" / "pr" / path.name, dry_run=dry_run, moved=moved)
        for path in sorted((old_epic_root / "runs").glob("*")) if (old_epic_root / "runs").exists() else []:
            if path.is_file():
                move_file(path, new_epic_root / "ops" / "runs" / path.name, dry_run=dry_run, moved=moved)
        for path in sorted((old_epic_root / "artifacts").glob("*")) if (old_epic_root / "artifacts").exists() else []:
            if path.is_file():
                move_file(path, new_epic_root / "ops" / "artifacts" / path.name, dry_run=dry_run, moved=moved)

        remove_empty_dirs(old_epic_root, dry_run=dry_run)

    remove_empty_dirs(handoffs_root, dry_run=dry_run)
    return moved, deleted


def migrate_archive(pm_root: Path, *, dry_run: bool) -> tuple[list[dict], list[str]]:
    moved: list[dict] = []
    deleted: list[str] = []
    archive_root = pm_root / "archive"
    if not archive_root.exists():
        return moved, deleted

    for epic_root in sorted(path for path in archive_root.iterdir() if path.is_dir()):
        for slice_root in sorted(path for path in epic_root.iterdir() if path.is_dir()):
            group_id = slice_root.name
            move_file(slice_root / f"{group_id}.md", slice_root / "slices" / f"{group_id}.md", dry_run=dry_run, moved=moved)
            delete_file(slice_root / f"{group_id}.json", dry_run=dry_run, deleted=deleted)

            for path in sorted((slice_root / "plans").glob("*.json")) if (slice_root / "plans").exists() else []:
                delete_file(path, dry_run=dry_run, deleted=deleted)
            compiled_dir = slice_root / "packets" / ".compiled"
            for path in sorted(compiled_dir.glob("*.json")) if compiled_dir.exists() else []:
                move_file(path, slice_root / "ops" / "handoffs" / path.name, dry_run=dry_run, moved=moved)
            for path in sorted((slice_root / "packets").glob("*.json")) if (slice_root / "packets").exists() else []:
                delete_file(path, dry_run=dry_run, deleted=deleted)

            if (slice_root / "pr").exists():
                for path in sorted((slice_root / "pr").glob("*")):
                    if path.is_file():
                        move_file(path, slice_root / "ops" / "pr" / path.name, dry_run=dry_run, moved=moved)
            if (slice_root / "runs").exists():
                for path in sorted((slice_root / "runs").glob("*")):
                    if path.is_file():
                        move_file(path, slice_root / "ops" / "runs" / path.name, dry_run=dry_run, moved=moved)
            if (slice_root / "artifacts").exists():
                for path in sorted((slice_root / "artifacts").glob("*")):
                    if path.is_file():
                        move_file(path, slice_root / "ops" / "artifacts" / path.name, dry_run=dry_run, moved=moved)

            remove_empty_dirs(slice_root, dry_run=dry_run)
    return moved, deleted


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    pm_root = root / ".pm-dawn"
    moved_active, deleted_active = migrate_active_epics(pm_root, dry_run=args.dry_run)
    moved_archive, deleted_archive = migrate_archive(pm_root, dry_run=args.dry_run)
    emit_json(
        {
            "repo_root": str(root),
            "dry_run": args.dry_run,
            "moved_count": len(moved_active) + len(moved_archive),
            "deleted_count": len(deleted_active) + len(deleted_archive),
            "moved": moved_active + moved_archive,
            "deleted": deleted_active + deleted_archive,
            "epics_root": str(pm_root / "epics"),
            "archive_root": str(pm_root / "archive"),
        }
    )


if __name__ == "__main__":
    main()
