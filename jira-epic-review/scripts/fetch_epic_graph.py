#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict

from common import emit_json_and_write_tmp, ensure_auth, issue_description, issue_parent_key, run_json


def fetch_issue(key: str) -> dict:
    return run_json(["jira", "workitem", "view", key, "--json"])


def fetch_links(key: str) -> list[dict]:
    data = run_json(["jira", "workitem", "link", "list", "--key", key, "--json"])
    return data.get("issueLinks", [])


def search_children(epic_key: str) -> list[str]:
    query = f'parent = {epic_key} OR "Epic Link" = {epic_key}'
    data = run_json(
        [
            "jira",
            "workitem",
            "search",
            "--jql",
            query,
            "--fields",
            "key,summary,status",
            "--json",
        ]
    )
    keys: list[str] = []
    for item in data:
        if isinstance(item, dict):
            key = item.get("key")
            if key:
                keys.append(key)
    return sorted(set(keys))


def simplify_issue(issue: dict, links: list[dict]) -> dict:
    fields = issue.get("fields", {})
    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "parent_key": issue_parent_key(issue),
        "description": issue_description(issue),
        "links": links,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a Jira epic and child work graph as normalized JSON.")
    parser.add_argument("epic_key")
    args = parser.parse_args()

    ensure_auth()

    epic = fetch_issue(args.epic_key)
    child_keys = search_children(args.epic_key)
    children = []
    statuses = defaultdict(int)
    for key in child_keys:
        issue = fetch_issue(key)
        links = fetch_links(key)
        record = simplify_issue(issue, links)
        children.append(record)
        statuses[record["status"]] += 1

    payload = {
        "epic_key": args.epic_key,
        "epic": simplify_issue(epic, fetch_links(args.epic_key)),
        "children": children,
        "child_keys": child_keys,
        "status_summary": dict(sorted(statuses.items())),
    }
    emit_json_and_write_tmp(payload, "epic-graph.json")


if __name__ == "__main__":
    main()
