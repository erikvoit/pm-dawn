#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import emit_json, ensure_auth, run_acli, write_temp_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Jira epic normalization changes through ACLI.")
    parser.add_argument("epic_key")
    parser.add_argument("--plan-json", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_auth()
    plan = json.loads(Path(args.plan_json).read_text())
    applied: dict[str, list[dict]] = {
        "created_links": [],
        "deleted_links": [],
        "updated_descriptions": [],
        "created_comments": [],
    }
    skipped_manual_review: list[dict] = []
    skipped_deferred: list[dict] = []

    for item in plan.get("delete_link_ids", []):
        if not item.get("auto_apply_eligible"):
            (skipped_deferred if item.get("confidence") == "low" else skipped_manual_review).append(item)
            continue
        link_id = item.get("id") or item.get("link_id")
        if not link_id:
            raise RuntimeError(f"eligible delete_link_ids item missing id: {item}")
        run_acli(["jira", "workitem", "link", "delete", "--id", str(link_id), "--yes"])
        applied["deleted_links"].append({"id": str(link_id), "source": item.get("source"), "target": item.get("target")})

    for link in plan.get("create_links", []):
        if not link.get("auto_apply_eligible"):
            (skipped_deferred if link.get("confidence") == "low" else skipped_manual_review).append(link)
            continue
        if not link.get("source") or not link.get("target"):
            raise RuntimeError(f"eligible create_links item missing source/target: {link}")
        run_acli(
            [
                "jira",
                "workitem",
                "link",
                "create",
                "--out",
                link["target"],
                "--in",
                link["source"],
                "--type",
                link.get("type", "Blocks"),
                "--yes",
            ]
        )
        applied["created_links"].append(link)

    for item in plan.get("update_descriptions", []):
        if not item.get("auto_apply_eligible"):
            (skipped_deferred if item.get("confidence") == "low" else skipped_manual_review).append(item)
            continue
        if not item.get("key") or "description" not in item:
            raise RuntimeError(f"eligible update_descriptions item missing key/description: {item}")
        path = write_temp_file(item["description"])
        try:
            run_acli(
                [
                    "jira",
                    "workitem",
                    "edit",
                    "--key",
                    item["key"],
                    "--description-file",
                    str(path),
                    "--yes",
                ]
            )
        finally:
            path.unlink(missing_ok=True)
        applied["updated_descriptions"].append({"key": item["key"]})

    for item in plan.get("create_comments", []):
        if not item.get("auto_apply_eligible"):
            (skipped_deferred if item.get("confidence") == "low" else skipped_manual_review).append(item)
            continue
        if not item.get("key") or "body" not in item:
            raise RuntimeError(f"eligible create_comments item missing key/body: {item}")
        path = write_temp_file(item["body"])
        try:
            run_acli(
                [
                    "jira",
                    "workitem",
                    "comment",
                    "create",
                    "--key",
                    item["key"],
                    "--body-file",
                    str(path),
                ]
            )
        finally:
            path.unlink(missing_ok=True)
        applied["created_comments"].append({"key": item["key"]})

    payload = {
        "epic_key": args.epic_key,
        "mode": plan.get("mode"),
        "summary": plan.get("summary", []),
        "applied": applied,
        "counts": {name: len(items) for name, items in applied.items()},
        "skipped_manual_review": skipped_manual_review,
        "skipped_deferred": skipped_deferred,
    }
    emit_json(payload)


if __name__ == "__main__":
    main()
