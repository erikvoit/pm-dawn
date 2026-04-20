#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import (
    canonical_body,
    collect_validation_lines,
    emit_json,
    find_existing_pr,
    load_pr_source,
    repo_root,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate canonical PR title/body from a .pm-dawn source.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--packet-id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--validation-line", action="append", default=[])
    parser.add_argument("--validation-file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    source = load_pr_source(root, args.epic_key, args.group_id, args.packet_id)
    existing_pr = find_existing_pr(root, source["current_branch"])
    validation_lines, validation_source = collect_validation_lines(
        root,
        source,
        explicit_lines=args.validation_line,
        validation_file=repo_root(args.validation_file) if args.validation_file else None,
        existing_pr=existing_pr,
    )
    body = canonical_body(source, validation_lines)
    write_text(repo_root(source["title_path"]), source["title"] + "\n")
    write_text(repo_root(source["body_path"]), body)
    emit_json(
        {
            "epic_key": args.epic_key,
            "group_id": args.group_id,
            "packet_id": args.packet_id,
            "title": source["title"],
            "body": body,
            "title_path": source["title_path"],
            "body_path": source["body_path"],
            "validation_lines": validation_lines,
            "validation_source": validation_source,
            "existing_pr": existing_pr,
        }
    )


if __name__ == "__main__":
    main()
