#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import REQUIRED_STORY_SECTIONS, story_quality


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a Jira epic graph after normalization.")
    parser.add_argument("epic_key")
    parser.add_argument("--plan-json")
    return parser.parse_args()


def run_fetch(epic_key: str) -> dict:
    script = Path(__file__).with_name("fetch_epic_graph.py")
    proc = subprocess.run(
        [sys.executable, str(script), epic_key],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def cycles(children: list[dict]) -> list[list[str]]:
    edges: dict[str, set[str]] = {}
    for child in children:
        edges[child["key"]] = {
            link["outwardIssueKey"]
            for link in child.get("links", [])
            if link.get("typeName") == "Blocks" and link.get("outwardIssueKey")
        }
    seen: set[str] = set()
    stack: set[str] = set()
    path: list[str] = []
    found: list[list[str]] = []

    def walk(node: str) -> None:
        seen.add(node)
        stack.add(node)
        path.append(node)
        for nxt in edges.get(node, set()):
            if nxt not in edges:
                continue
            if nxt not in seen:
                walk(nxt)
            elif nxt in stack:
                idx = path.index(nxt)
                found.append(path[idx:] + [nxt])
        stack.remove(node)
        path.pop()

    for key in sorted(edges):
        if key not in seen:
            walk(key)
    return found


def main() -> None:
    args = parse_args()
    graph = run_fetch(args.epic_key)
    children = {child["key"]: child for child in graph["children"]}
    failures: list[str] = []

    plan = {}
    if args.plan_json:
        plan = json.loads(Path(args.plan_json).read_text())

    for item in [entry for entry in plan.get("create_links", []) if entry.get("auto_apply_eligible")]:
        links = children.get(item["source"], {}).get("links", [])
        if not any(link.get("outwardIssueKey") == item["target"] and link.get("typeName") == item.get("type", "Blocks") for link in links):
            failures.append(f"missing expected link {item['source']} -> {item['target']}")

    for item in [entry for entry in plan.get("delete_link_ids", []) if entry.get("auto_apply_eligible")]:
        link_id = item.get("id") or item.get("link_id")
        for child in children.values():
            if any(link.get("id") == str(link_id) for link in child.get("links", [])):
                failures.append(f"link {link_id} still exists")

    for item in [entry for entry in plan.get("update_descriptions", []) if entry.get("auto_apply_eligible")]:
        description = children.get(item["key"], {}).get("description", "")
        quality = story_quality(description)
        for section in REQUIRED_STORY_SECTIONS:
            if section in quality["missing_sections"]:
                failures.append(f"{item['key']} description missing section: {section}")
            elif section in quality["empty_sections"]:
                failures.append(f"{item['key']} description has empty section: {section}")

    for item in [entry for entry in plan.get("create_comments", []) if entry.get("auto_apply_eligible")]:
        proc = subprocess.run(
            [
                "acli",
                "jira",
                "workitem",
                "comment",
                "list",
                "--key",
                item["key"],
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            failures.append(f"could not verify comments for {item['key']}: {proc.stderr.strip() or proc.stdout.strip()}")
            continue
        comments_payload = json.loads(proc.stdout or "{}")
        if isinstance(comments_payload, dict):
            comments = comments_payload.get("comments", [])
        elif isinstance(comments_payload, list):
            comments = comments_payload
        else:
            comments = []
        expected = item["body"].strip()
        matched = False
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            body = comment.get("body")
            if isinstance(body, str) and expected in body:
                matched = True
                break
            if isinstance(body, dict):
                body_text = json.dumps(body, sort_keys=True)
                if expected in body_text:
                    matched = True
                    break
        if not matched:
            failures.append(f"missing expected comment on {item['key']}")

    found_cycles = cycles(list(children.values()))
    if found_cycles:
        failures.extend(f"blocks cycle detected: {' -> '.join(cycle)}" for cycle in found_cycles)

    payload = {
        "epic_key": args.epic_key,
        "ok": not failures,
        "failures": failures,
        "cycles": found_cycles,
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
