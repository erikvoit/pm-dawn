#!/usr/bin/env python3
"""Resolve a slice by name and archive or delete its .pm-dawn artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import emit_json, repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive or delete .pm-dawn slice artifacts by slice name.")
    parser.add_argument("group_id", help="Slice/group id such as scaffold_or_proof_3.")
    parser.add_argument("--epic-key", help="Optional epic key to disambiguate the slice name.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=("archive", "delete"), required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _find_matches(root: Path, group_id: str, epic_key: str | None) -> list[str]:
    epics_root = root / ".pm-dawn" / "epics"
    if not epics_root.exists():
        return []
    epics = [epic_key] if epic_key else [path.name for path in epics_root.iterdir() if path.is_dir()]
    matches: list[str] = []
    for epic in epics:
        epic_root = epics_root / epic
        if not epic_root.exists():
            continue
        candidates = [
            epic_root / "slices" / f"{group_id}.md",
            epic_root / "plans" / f"{group_id}.plan.md",
            epic_root / "ops" / "runs" / f"{group_id}.json",
        ]
        if any(path.exists() for path in candidates):
            matches.append(epic)
    return sorted(matches)


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    matches = _find_matches(root, args.group_id, args.epic_key)
    if not matches:
        raise SystemExit(f"no slice artifacts found for {args.group_id}")
    if len(matches) > 1:
        raise SystemExit(
            f"slice name {args.group_id} is ambiguous across epics: {', '.join(matches)}; pass --epic-key"
        )

    epic_key = matches[0]
    cmd = [
        sys.executable,
        str(Path(__file__).with_name("cleanup_slice_artifacts.py")),
        epic_key,
        args.group_id,
        "--repo-root",
        str(root),
        "--mode",
        args.mode,
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    payload["resolved_epic_key"] = epic_key
    emit_json(payload)


if __name__ == "__main__":
    main()
