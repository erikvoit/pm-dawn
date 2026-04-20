#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path

from common import categorize_summary, emit_json_and_write_tmp, graph_epic_key, story_quality


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a normalized Jira epic graph.")
    parser.add_argument("graph_json")
    return parser.parse_args()


def blocks_out(link: dict) -> str | None:
    if link.get("typeName") != "Blocks":
        return None
    return link.get("outwardIssueKey")


def inbound_only(link: dict) -> bool:
    return link.get("typeName") == "Blocks" and not link.get("outwardIssueKey")


def find_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    visited: set[str] = set()
    stack: set[str] = set()
    path: list[str] = []
    cycles: list[list[str]] = []

    def walk(node: str) -> None:
        visited.add(node)
        stack.add(node)
        path.append(node)
        for nxt in edges.get(node, set()):
            if nxt not in visited:
                walk(nxt)
            elif nxt in stack:
                idx = path.index(nxt)
                cycles.append(path[idx:] + [nxt])
        stack.remove(node)
        path.pop()

    for node in sorted(edges):
        if node not in visited:
            walk(node)
    return cycles


def reachable(start: str, edges: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    queue: deque[str] = deque(edges.get(start, set()))
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(edges.get(node, set()))
    return seen


def confidence_for_missing(source_tags: set[str], target_tags: set[str]) -> tuple[str, str, list[str]]:
    evidence_sources = ["graph_rule"]
    if "contract" in source_tags and ({"runtime", "registry", "scheduler"} & target_tags):
        return "high", "direct contract-to-runtime dependency follows a strong architecture rule", evidence_sources
    if "registry" in source_tags and "runtime" in target_tags:
        return "high", "registry-to-runtime dependency follows a strong composition rule", evidence_sources
    if "control" in source_tags and "ux" in target_tags:
        return "high", "control semantics should precede operator UX", evidence_sources
    if "replay" in source_tags and "ux" in target_tags:
        return "high", "replay semantics should precede replay/debug UX", evidence_sources
    return "medium", "dependency is plausible but depends on summary-based category inference", evidence_sources + ["summary_inference"]


def confidence_for_reversed(source_tags: set[str], target_tags: set[str]) -> tuple[str, str, list[str]]:
    evidence_sources = ["graph_rule", "summary_inference"]
    if "runtime" in source_tags and "contract" in target_tags:
        return "high", "implementation-to-contract direction violates a strong architecture rule", evidence_sources
    return "medium", "link direction looks wrong but still depends on summary-based role inference", evidence_sources


def confidence_for_redundant() -> tuple[str, str, list[str]]:
    return "medium", "redundancy depends on transitive graph structure and should be reviewed", ["transitive_graph"]


def confidence_for_soft() -> tuple[str, str, list[str]]:
    return "medium", "relationship looks informative rather than blocking, but may still encode sequencing", ["graph_rule", "summary_inference"]


def confidence_for_normalization(quality: dict[str, object]) -> tuple[str, str, list[str]]:
    if quality["missing_sections"] or quality["empty_sections"]:
        return "high", "required story template sections are missing or empty", ["story_quality"]
    return "medium", "story template exists but some sections are still too thin for handoff", ["story_quality"]


def confidence_for_misplacement() -> tuple[str, str, list[str]]:
    return "low", "epic misplacement is inferred mostly from wording and should be reviewed manually", ["summary_inference"]


def main() -> None:
    args = parse_args()
    graph = json.loads(Path(args.graph_json).read_text())
    epic_key = graph_epic_key(graph)
    children = graph["children"]
    child_keys = {child["key"] for child in children}
    summaries = {child["key"]: (child.get("summary") or "") for child in children}
    tags_by_key = {key: categorize_summary(summary) for key, summary in summaries.items()}

    edges: dict[str, set[str]] = defaultdict(set)
    link_ids: dict[tuple[str, str], str] = {}
    likely_reversed: list[dict] = []
    needs_normalization: list[dict] = []
    weak_descriptions: list[dict] = []
    repo_triggers: set[str] = set()

    for child in children:
        key = child["key"]
        quality = story_quality(child.get("description") or "")
        if not quality["is_normalized"]:
            confidence, confidence_reason, evidence_sources = confidence_for_normalization(quality)
            needs_normalization.append(
                {
                    "key": key,
                    "missing_sections": quality["missing_sections"],
                    "empty_sections": quality["empty_sections"],
                    "short_sections": quality["short_sections"],
                    "confidence": confidence,
                    "confidence_reason": confidence_reason,
                    "evidence_sources": evidence_sources,
                }
            )
        if quality["is_weak"]:
            confidence, confidence_reason, evidence_sources = confidence_for_normalization(quality)
            weak_descriptions.append(
                {
                    "key": key,
                    "missing_sections": quality["missing_sections"],
                    "empty_sections": quality["empty_sections"],
                    "short_sections": quality["short_sections"],
                    "confidence": confidence,
                    "confidence_reason": confidence_reason,
                    "evidence_sources": evidence_sources,
                }
            )

        if tags_by_key[key] & {"contract", "registry", "runtime", "control", "replay", "scheduler", "api"}:
            repo_triggers.add(key)

        for link in child.get("links", []):
            outward = blocks_out(link)
            if outward:
                edges[key].add(outward)
                link_ids[(key, outward)] = str(link["id"])
                target_tags = tags_by_key.get(outward, set())
                source_tags = tags_by_key[key]
                reason = None
                if "ux" in source_tags and target_tags & {"api", "runtime", "registry", "contract", "replay", "control"}:
                    reason = "UI or operator story blocks a backend or runtime dependency"
                elif "runtime" in source_tags and "contract" in target_tags:
                    reason = "implementation story blocks a contract or interface story"
                elif "hardening" in source_tags and target_tags & {"runtime", "scheduler", "control", "api"}:
                    reason = "hardening story blocks a lower-level primitive it likely depends on"
                if reason:
                    confidence, confidence_reason, evidence_sources = confidence_for_reversed(source_tags, target_tags)
                    likely_reversed.append(
                        {
                            "source": key,
                            "target": outward,
                            "reason": reason,
                            "confidence": confidence,
                            "confidence_reason": confidence_reason,
                            "evidence_sources": evidence_sources,
                        }
                    )
            elif inbound_only(link):
                repo_triggers.add(key)

    cycles = find_cycles({k: {v for v in vals if v in child_keys} for k, vals in edges.items()})

    missing_candidates: list[dict] = []
    for source, source_tags in tags_by_key.items():
        for target, target_tags in tags_by_key.items():
            if source == target:
                continue
            if target in edges.get(source, set()) or source in edges.get(target, set()):
                continue

            reason = None
            if "contract" in source_tags and ({"runtime", "registry", "scheduler"} & target_tags):
                reason = "contract or interface story should directly block downstream runtime or registry work"
            elif "registry" in source_tags and "runtime" in target_tags:
                reason = "registry or composition story should block runtime adapter registration work"
            elif "control" in source_tags and "ux" in target_tags:
                reason = "runtime control semantics should block operator-control UX"
            elif "replay" in source_tags and "ux" in target_tags:
                reason = "checkpoint or replay semantics should block replay or debug UX"
            if reason is None:
                continue
            confidence, confidence_reason, evidence_sources = confidence_for_missing(source_tags, target_tags)
            missing_candidates.append(
                {
                    "source": source,
                    "target": target,
                    "type": "Blocks",
                    "reason": reason,
                    "confidence": confidence,
                    "confidence_reason": confidence_reason,
                    "evidence_sources": evidence_sources,
                }
            )

    redundant_candidates: list[dict] = []
    for source, targets in edges.items():
        for target in sorted(targets):
            indirect_paths = reachable(source, {k: set(v) - {target} if k == source else set(v) for k, v in edges.items()})
            if target not in indirect_paths:
                continue
            source_tags = tags_by_key.get(source, set())
            if source_tags & {"contract", "registry", "control"}:
                continue
            confidence, confidence_reason, evidence_sources = confidence_for_redundant()
            redundant_candidates.append(
                {
                    "source": source,
                    "target": target,
                    "link_id": link_ids.get((source, target)),
                    "reason": "link appears transitively redundant and does not encode a clear architecture boundary",
                    "confidence": confidence,
                    "confidence_reason": confidence_reason,
                    "evidence_sources": evidence_sources,
                }
            )

    soft_coupling_candidates: list[dict] = []
    for source, targets in edges.items():
        source_tags = tags_by_key.get(source, set())
        for target in targets:
            target_tags = tags_by_key.get(target, set())
            if "ux" in source_tags and "ux" in target_tags:
                confidence, confidence_reason, evidence_sources = confidence_for_soft()
                soft_coupling_candidates.append(
                    {
                        "source": source,
                        "target": target,
                        "link_id": link_ids.get((source, target)),
                        "recommended_type": "Relates",
                        "reason": "relationship looks informative but not sequencing-critical",
                        "confidence": confidence,
                        "confidence_reason": confidence_reason,
                        "evidence_sources": evidence_sources,
                    }
                )

    epic_misplacement_candidates = []
    for child in children:
        summary = summaries[child["key"]].lower()
        if "hardening" in summary or "release" in summary:
            confidence, confidence_reason, evidence_sources = confidence_for_misplacement()
            epic_misplacement_candidates.append(
                {
                    "key": child["key"],
                    "reason": "story summary suggests hardening or release scope rather than runtime-abstraction scope",
                    "confidence": confidence,
                    "confidence_reason": confidence_reason,
                    "evidence_sources": evidence_sources,
                }
            )

    payload = {
        "epic_key": epic_key,
        "missing_dependency_candidates": sorted(missing_candidates, key=lambda item: (item["source"], item["target"])),
        "likely_reversed_links": sorted(likely_reversed, key=lambda item: (item["source"], item["target"])),
        "redundant_dependency_candidates": sorted(redundant_candidates, key=lambda item: (item["source"], item["target"])),
        "soft_coupling_candidates": sorted(soft_coupling_candidates, key=lambda item: (item["source"], item["target"])),
        "suspicious_cycles": cycles,
        "stories_needing_description_normalization": sorted(needs_normalization, key=lambda item: item["key"]),
        "stories_with_weak_descriptions": sorted(weak_descriptions, key=lambda item: item["key"]),
        "epic_misplacement_candidates": sorted(epic_misplacement_candidates, key=lambda item: item["key"]),
        "repo_inspection_triggers": sorted(repo_triggers),
    }
    emit_json_and_write_tmp(payload, "epic-analysis.json")


if __name__ == "__main__":
    main()
