#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import (
    emit_json,
    explicit_paths_from_markdown,
    keyword_tokens,
    load_handoff,
    read_optional_text,
    repo_root,
    search_candidates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect repo context relevant to a .pm-dawn slice.")
    parser.add_argument("epic_key")
    parser.add_argument("group_id")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def build_inspect_payload(root, args_epic_key: str, args_group_id: str, handoff: dict, markdown: str | None) -> dict:
    explicit_paths = explicit_paths_from_markdown(markdown, root)
    keywords = keyword_tokens(handoff, markdown)
    candidates = search_candidates(root, handoff.get("repo_surfaces", []), keywords)

    likely_files = []
    for item in explicit_paths + candidates:
        if item not in likely_files:
            likely_files.append(item)
    for surface in handoff.get("repo_surfaces", []):
        if any(item == surface or item.startswith(f"{surface}/") for item in likely_files):
            continue
        likely_files.append(surface)

    not_to_change: list[str] = []
    unresolved: list[str] = []
    if markdown and "/runs/{run_id}/{action}" in markdown:
        route_candidates = [item for item in candidates if item.endswith("routes/runs.py")]
        if route_candidates and route_candidates[0] not in likely_files:
            not_to_change.append(route_candidates[0])
    if "runtime" in keywords and not any("runtime" in item.lower() for item in likely_files if not item.startswith("tests/")):
        unresolved.append("No concrete non-test runtime seam candidate found from the current hints.")

    return {
        "epic_key": args_epic_key,
        "group_id": args_group_id,
        "explicit_paths": explicit_paths,
        "keywords": keywords,
        "likely_files": likely_files[:20],
        "files_not_to_change": sorted(dict.fromkeys(not_to_change)),
        "unresolved_ambiguity": unresolved,
        "source_markdown_present": markdown is not None,
    }


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    handoff, paths = load_handoff(root, args.epic_key, args.group_id)
    markdown = read_optional_text(paths.slice_md)
    payload = build_inspect_payload(root, args.epic_key, args.group_id, handoff, markdown)
    emit_json(payload)


if __name__ == "__main__":
    main()
