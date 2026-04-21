#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.bootstrap import bootstrap_workspace


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate .pm-dawn handoff artifacts from an epic review plan.")
    parser.add_argument("epic_key")
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--review-json")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def list_lines(items: list[str], default: str = "- None") -> str:
    if not items:
        return default
    return "\n".join(f"- {item}" for item in items)


def render_group_md(epic_key: str, group: dict) -> str:
    secondary = ", ".join(group.get("secondary_issues", [])) or "None"
    pr_traceability = group.get("pr_traceability", {})
    additional = ", ".join(pr_traceability.get("additional_issues", [])) or "None"
    source_context = group.get("source_context", {})
    return f"""# {epic_key} / {group['group_id']}

Group ID: {group['group_id']}
Primary Jira Key: {group['primary_issue']}
Secondary Jira Keys: {secondary}

Goal:
{list_lines([group['goal']])}

Why This Slice Exists:
{list_lines(group.get('risks', []))}

Branch Recommendation:
- {group['branch_name']}

PR Traceability:
- Primary: {pr_traceability.get('primary_issue', group['primary_issue'])}
- Additional: {additional}
- PR body should reference all covered Jira keys.

Entry Criteria:
{list_lines(group.get('entry_criteria', []))}

Exit Criteria:
{list_lines(group.get('exit_criteria', []))}

Repo Surfaces:
{list_lines(group.get('repo_surfaces', []))}

Implementation Steps:
{list_lines(group.get('implementation_steps', []))}

Validation Steps:
{list_lines(group.get('validation_steps', []))}

Risks and Constraints:
{list_lines(group.get('risks', []))}

Open Questions:
{list_lines(group.get('open_questions', []))}

Source Review Context:
- Derived from epic review of {epic_key} on {source_context.get('epic_review_date', 'unknown-date')}.
- {source_context.get('implementation_group_reason', 'No additional context recorded.')}
"""


def render_index_md(epic_key: str, manifest: dict, groups: list[dict], plan: dict) -> str:
    lines = [
        f"# {epic_key} handoff index",
        "",
        f"Review Date: {manifest['generated_at'].split('T')[0]}",
        "",
        "Implementation Groups:",
    ]
    for group in groups:
        lines.append(f"- {group['group_id']} ({', '.join([group['primary_issue'], *group.get('secondary_issues', [])]).rstrip(', ')})")
        lines.append(f"  - Goal: {group['goal']}")
        lines.append(f"  - Branch: {group['branch_name']}")
    lines.extend(
        [
            "",
            "Manual Review Required:",
            list_lines([item.get("reason") or item.get("policy_reason", "Review required") for item in plan.get("manual_review_required", [])]),
            "",
            "Deferred Changes:",
            list_lines([item.get("reason") or item.get("policy_reason", "Deferred") for item in plan.get("deferred_changes", [])]),
            "",
            "Assumptions:",
            list_lines(plan.get("assumptions", [])),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    bootstrap_workspace(repo_root, create_profile=True)
    plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    review = json.loads(Path(args.review_json).read_text(encoding="utf-8")) if args.review_json else {}

    epic_root = repo_root / ".pm-dawn" / "epics" / args.epic_key
    slices_dir = epic_root / "slices"
    artifacts_dir = epic_root / "ops" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    manifest = dict(plan.get("epic_handoff_manifest", {}))
    manifest.setdefault("epic_key", args.epic_key)
    manifest.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    manifest["source_artifacts"] = {
        "plan_json": str(Path(args.plan_json).resolve()),
        "review_json": str(Path(args.review_json).resolve()) if args.review_json else None,
    }

    handoffs = plan.get("implementation_handoffs", [])

    write_text(epic_root / "index.md", render_index_md(args.epic_key, manifest, handoffs, plan))

    for handoff in handoffs:
        group_md = render_group_md(args.epic_key, handoff)
        write_text(slices_dir / f"{handoff['group_id']}.md", group_md)

    timestamp = manifest["generated_at"].replace(":", "").replace("-", "")
    write_json(artifacts_dir / f"{timestamp}-plan.json", plan)
    if review:
        write_json(artifacts_dir / f"{timestamp}-review.json", review)

    output = {
        "epic_key": args.epic_key,
        "epic_root": str(epic_root),
        "groups": [item["group_id"] for item in handoffs],
        "files_written": sorted(str(path) for path in epic_root.rglob("*") if path.is_file()),
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
