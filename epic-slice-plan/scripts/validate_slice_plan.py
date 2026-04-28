#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import emit_json, repo_root
from pm_dawn_core.plan import validate_slice_plan_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated slice plan and packet artifacts.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    try:
        payload = validate_slice_plan_artifacts(root, args.epic_key, args.group_id)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    emit_json(payload)
    if payload["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
