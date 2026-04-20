#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from common import emit_json_and_write_tmp, require_matching_epic


def run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return ""
    return proc.stdout


def grep_main(repo: Path, pattern: str) -> list[str]:
    output = run(["git", "grep", "-n", "-i", pattern, "main"], repo)
    return [line for line in output.splitlines() if line.strip()][:50]


def evidence_score(lines: list[str]) -> tuple[int, list[str]]:
    score = 0
    anchors: list[str] = []
    for line in lines:
        lower = line.lower()
        anchors.append(line)
        if any(token in lower for token in ("/tests/", "test_", "routes/", "providers.py", "protocol", "runtime-", "runtime_")):
            score += 2
        elif any(token in lower for token in ("readme", "docs/", "agents.md")):
            score += 0
        else:
            score += 1
    return score, anchors[:10]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect repo context relevant to a Jira epic.")
    parser.add_argument("epic_key")
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--graph-json")
    parser.add_argument("--analysis-json")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = Path(args.repo_path).resolve()
    analysis = {}
    if args.analysis_json:
        analysis = json.loads(Path(args.analysis_json).read_text())
        require_matching_epic(args.epic_key, analysis, str(args.analysis_json))
    triggers = analysis.get("repo_inspection_triggers", [])

    result = {
        "epic_key": args.epic_key,
        "repo_path": str(repo),
        "inspected": False,
        "reason": "",
        "implemented_on_main": [],
        "likely_missing_on_main": [],
        "inconclusive": [],
        "architectural_seams": [],
        "file_anchors": [],
        "issue_evidence": {},
    }

    if not args.force and not triggers:
        result["reason"] = "graph analysis did not identify a meaningful repo-inspection trigger"
        emit_json_and_write_tmp(result, "repo-context.json")
        return

    if not (repo / ".git").exists():
        result["reason"] = "repo path is not a git working tree"
        emit_json_and_write_tmp(result, "repo-context.json")
        return

    graph = json.loads(Path(args.graph_json).read_text()) if args.graph_json else {}
    if graph:
        require_matching_epic(args.epic_key, graph, str(args.graph_json))
    children = graph.get("children", [])

    seam_tokens = ["RuntimeGateway", "protocol", "provider", "adapter", "registry", "stream", "replay", "checkpoint", "lane", "scheduler"]
    seam_hits: list[str] = []
    for token in seam_tokens:
        seam_hits.extend(grep_main(repo, token))

    for child in children:
        key = child["key"]
        patterns = [key, child.get("summary", "")]
        hits: list[str] = []
        for pattern in patterns:
            token = pattern.strip()
            if len(token) < 4:
                continue
            hits.extend(grep_main(repo, token))
        score, anchors = evidence_score(sorted(set(hits)))
        result["file_anchors"].extend(anchors)
        if score >= 4:
            status = "implemented_on_main"
            result["implemented_on_main"].append(key)
        elif score == 0:
            status = "likely_missing_on_main"
            result["likely_missing_on_main"].append(key)
        else:
            status = "inconclusive"
            result["inconclusive"].append(key)
        result["issue_evidence"][key] = {"status": status, "anchors": anchors}

    result["inspected"] = True
    result["reason"] = "repo inspection enabled and relevant to epic analysis"
    result["architectural_seams"] = sorted(set(seam_hits))[:25]
    result["file_anchors"] = sorted(set(result["file_anchors"]))[:50]
    emit_json_and_write_tmp(result, "repo-context.json")


if __name__ == "__main__":
    main()
