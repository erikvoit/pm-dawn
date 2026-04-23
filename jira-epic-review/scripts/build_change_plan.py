#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from common import (
    REQUIRED_STORY_SECTIONS,
    categorize_summary,
    emit_json_and_write_tmp,
    issue_description,
    load_project_profile,
    repo_root,
    require_matching_epic,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a machine-readable change plan for a Jira epic review.")
    parser.add_argument("epic_key")
    parser.add_argument("--graph-json", required=True)
    parser.add_argument("--analysis-json", required=True)
    parser.add_argument("--repo-json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=("review", "apply"), default="review")
    return parser.parse_args()


def issue_map(graph: dict) -> dict[str, dict]:
    return {child["key"]: child for child in graph.get("children", [])}


def normalize_repo_evidence(repo: dict) -> dict[str, dict]:
    evidence = repo.get("issue_evidence") or {}
    if evidence:
        return evidence
    normalized: dict[str, dict] = {}
    for key in repo.get("implemented_on_main", []):
        normalized[key] = {"status": "implemented_on_main", "anchors": []}
    for key in repo.get("likely_missing_on_main", []):
        normalized[key] = {"status": "likely_missing_on_main", "anchors": []}
    for key in repo.get("inconclusive", []):
        normalized[key] = {"status": "inconclusive", "anchors": []}
    return normalized


def adjust_confidence(base: str, repo_status: str | None) -> str:
    order = ["low", "medium", "high"]
    idx = order.index(base)
    if repo_status == "inconclusive":
        idx = max(0, idx - 1)
    elif repo_status in {"implemented_on_main", "likely_missing_on_main"}:
        idx = min(len(order) - 1, idx + 1)
    return order[idx]


GENERIC_NORMALIZATION_MARKERS = (
    "this story previously lacked",
    "this normalization is intended",
    "preserve the existing intent",
    "the story describes clear, observable completion conditions",
)


def clean_sentence(text: str) -> str:
    value = re.sub(r"\s+", " ", text.strip())
    if not value:
        return value
    if value[-1] not in ".!?":
        value += "."
    return value


def first_meaningful_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith(":"):
            continue
        stripped = stripped.lstrip("-* ").strip()
        lowered = stripped.lower()
        if any(marker in lowered for marker in GENERIC_NORMALIZATION_MARKERS):
            continue
        return clean_sentence(stripped)
    return None


def linked_issue_keys(issue: dict) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    blocked: list[str] = []
    for link in issue.get("issuelinks", []):
        link_type = ((link.get("type") or {}).get("name") or "").lower()
        if link_type != "blocks":
            continue
        inward = link.get("inwardIssue")
        outward = link.get("outwardIssue")
        if isinstance(inward, dict) and inward.get("key"):
            blockers.append(inward["key"])
        if isinstance(outward, dict) and outward.get("key"):
            blocked.append(outward["key"])
    return blockers, blocked


def seam_labels(tags: set[str]) -> list[str]:
    labels: list[str] = []
    if "contract" in tags:
        labels.append("shared contract")
    if "api" in tags:
        labels.append("API")
    if "runtime" in tags:
        labels.append("runtime")
    if "ux" in tags:
        labels.append("TUI/UX")
    if "replay" in tags:
        labels.append("replay")
    if "hardening" in tags:
        labels.append("safety")
    return labels


def specific_scope_bullets(summary: str, tags: set[str]) -> list[str]:
    bullets = [clean_sentence(summary)]
    if "contract" in tags:
        bullets.append("Keep the deliverable centered on shared contract semantics consumed downstream.")
    if "api" in tags and "ux" not in tags:
        bullets.append("Limit changes to the relevant API seam and its required schema or boundary shaping.")
    if "ux" in tags:
        bullets.append("Limit changes to the terminal operator workflow that consumes the approved replay/API seam.")
    if "replay" in tags:
        bullets.append("Keep the behavior deterministic and grounded in persisted replay state rather than live execution.")
    if "hardening" in tags:
        bullets.append("Implement guardrails that fail closed instead of allowing unsafe replay behavior.")
    return bullets[:3]


def specific_out_of_scope_bullets(tags: set[str]) -> list[str]:
    bullets = ["Adjacent work that belongs in sibling stories or later slices."]
    if "ux" in tags:
        bullets.append("New backend behavior beyond the replay/debug seam needed by this story.")
    elif "api" in tags or "contract" in tags:
        bullets.append("Operator-facing UX work that should consume this seam later instead of being bundled here.")
    elif "hardening" in tags:
        bullets.append("Broader hardening work unrelated to replay safety or fail-closed execution.")
    else:
        bullets.append("Changes to unrelated API, UI, runtime, or hardening surfaces.")
    return bullets


def specific_acceptance_bullets(summary: str, tags: set[str]) -> list[str]:
    bullets = ["The seam described in the summary is implemented in an observable, testable way."]
    if "replay" in tags:
        bullets.append("Replay behavior remains deterministic and does not require inventing live execution semantics.")
    if "ux" in tags:
        bullets.append("The operator-facing behavior is explicit about replay-only limitations.")
    if "hardening" in tags:
        bullets.append("Unsafe replay paths fail closed instead of silently executing live side effects.")
    if "contract" in tags:
        bullets.append("Downstream consumers can rely on shared contract logic instead of duplicating it ad hoc.")
    return bullets[:3]


def specific_test_bullets(tags: set[str]) -> list[str]:
    bullets = ["Add focused tests that cover the behavior or contract described by this story."]
    if "ux" in tags:
        bullets.append("Cover the replay/debug workflow from the TUI seam rather than only isolated render behavior.")
    if "api" in tags:
        bullets.append("Validate API boundary handling and any schema shaping introduced by this story.")
    if "contract" in tags:
        bullets.append("Cover shared contract helpers or normalization logic in core tests.")
    if "hardening" in tags:
        bullets.append("Add negative-path tests that prove unsafe replay behavior is blocked.")
    return bullets[:3]


def specific_dependency_bullets(blockers: list[str], blocked: list[str]) -> list[str]:
    bullets: list[str] = []
    if blockers:
        bullets.append(f"Blocked by: {', '.join(sorted(blockers))}.")
    if blocked:
        bullets.append(f"Upstream of: {', '.join(sorted(blocked))}.")
    if not bullets:
        bullets.append("No explicit Jira blockers are linked yet; confirm sequencing before apply if this story is still in planning.")
    return bullets


def render_description(issue: dict, analysis_entry: dict) -> tuple[str | None, str | None]:
    summary = clean_sentence(issue["summary"])
    current_desc = issue_description(issue)
    seed = first_meaningful_line(current_desc) or summary
    tags = categorize_summary(issue["summary"])
    blockers, blocked = linked_issue_keys(issue)

    enough_signal = bool(tags or blockers or blocked or (seed and seed != summary))
    if not enough_signal:
        return None, (
            "Not enough story-specific signal to generate a useful normalized description. "
            "Needs human direction before apply."
        )

    context_bullets = [seed]
    seam_text = ", ".join(seam_labels(tags))
    if seam_text:
        context_bullets.append(f"This story is primarily a {seam_text} seam within the epic.")
    elif blockers or blocked:
        context_bullets.append("This story's role is inferred mainly from its dependency position in the epic.")

    sections = {
        "Context": context_bullets,
        "Scope": specific_scope_bullets(summary, tags),
        "Out of scope": specific_out_of_scope_bullets(tags),
        "Acceptance criteria": specific_acceptance_bullets(summary, tags),
        "Test plan": specific_test_bullets(tags),
        "Dependencies": specific_dependency_bullets(blockers, blocked),
    }
    rendered = [summary, ""]
    for header in REQUIRED_STORY_SECTIONS:
        rendered.append(f"{header}:")
        for bullet in sections[header]:
            rendered.append(f"- {bullet}")
        rendered.append("")
    return "\n".join(rendered).strip() + "\n", None


def comment_for_link(change: dict) -> str:
    return (
        f"Normalized dependency graph: `{change['source']}` now blocks `{change['target']}`.\n\n"
        f"Reason: {change['reason']}"
    )


def comment_for_description(key: str) -> str:
    return (
        f"Updated `{key}` to use the standard planning template with story-specific "
        f"Context, Scope, Out of scope, Acceptance criteria, Test plan, and Dependencies."
    )


def policy_for_item(change_type: str, confidence: str, item: dict) -> tuple[bool, str]:
    if confidence == "low":
        return False, "low-confidence changes are deferred for manual decision"
    if confidence == "medium":
        return False, "medium-confidence changes require manual review before apply"
    if change_type == "create_links":
        return item.get("type") == "Blocks", "only high-confidence additive Blocks links are auto-applied"
    if change_type == "delete_link_ids":
        return False, "link deletions stay manual-review-only in this policy version"
    if change_type == "update_descriptions":
        safe = bool(item.get("missing_sections") or item.get("empty_sections"))
        return safe, "template-completion description updates are auto-applied only when required sections are missing or empty"
    if change_type == "create_comments":
        return False, "comment eligibility is determined from the paired mutation item"
    return False, "unsupported change type"


def mutation_record(change_type: str, item: dict, repo_evidence: dict[str, dict]) -> dict:
    record = dict(item)
    record["change_type"] = change_type
    issue_key = item.get("key") or item.get("source")
    repo_status = repo_evidence.get(issue_key, {}).get("status")
    base_confidence = item.get("confidence", "medium")
    record["confidence"] = adjust_confidence(base_confidence, repo_status) if repo_status else base_confidence
    record["confidence_reason"] = item.get("confidence_reason", "confidence inferred from analyzer heuristics")
    record["evidence_sources"] = item.get("evidence_sources", [])
    if repo_status and repo_status not in record["evidence_sources"]:
        record["evidence_sources"] = [*record["evidence_sources"], f"repo_{repo_status}"]
    auto_apply_eligible, policy_reason = policy_for_item(change_type, record["confidence"], record)
    record["auto_apply_eligible"] = auto_apply_eligible
    record["policy_reason"] = policy_reason
    return record


def group_label(prefix: str, index: int) -> str:
    return f"{prefix}_{index}"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "implementation-slice"


def infer_repo_surfaces(stories: list[str], issues: dict[str, dict], profile: dict) -> list[str]:
    surfaces: set[str] = set()
    combined_tags: set[str] = set()
    for story in stories:
        combined_tags |= categorize_summary(issues[story].get("summary") or "")
    tag_surfaces = profile.get("review", {}).get("tag_surfaces", {})
    for tag in combined_tags:
        for surface in tag_surfaces.get(tag, []):
            surfaces.add(surface)
    return sorted(surfaces)


def infer_implementation_steps(group: dict, issues: dict) -> list[str]:
    stories = group["stories"]
    summaries = [issues[key].get("summary") or key for key in stories]
    steps = [f"Implement the slice represented by {', '.join(stories)}."]
    for summary in summaries[:3]:
        steps.append(summary.rstrip("."))
    return steps


def infer_validation_steps(group: dict) -> list[str]:
    label = group["group_id"]
    if label.startswith("contract_foundation"):
        return ["Run contract tests.", "Run registry integration tests.", "Validate API compatibility with the shared seam."]
    if label.startswith("adapter_core"):
        return ["Run adapter tests.", "Run integration tests through the runtime seam.", "Validate event/control behavior."]
    if label.startswith("scaffold_or_proof"):
        return ["Run contract conformance tests.", "Run registry discovery tests.", "Validate unsupported-operation behavior."]
    return ["Run focused tests for the slice.", "Validate upstream and downstream integration points."]


def branch_name_for_group(group: dict, issues: dict, profile: dict) -> str:
    primary = group["stories"][0]
    label = group["label"]
    suffix = slugify(label.replace(" ", "-"))
    branches = profile.get("branches", {})
    branch_type = branches.get("default_type") or branches.get("allowed_prefixes", ["feature"])[0]
    template = str(branches.get("template", "<type>/<jira-key>-<slug>"))
    return (
        template.replace("<type>", branch_type)
        .replace("<jira-key>", primary)
        .replace("<slug>", suffix)
    )


def build_handoffs(
    epic_key: str,
    implementation_groups: list[dict],
    issues: dict[str, dict],
    manual_review_required: list[dict],
    deferred_changes: list[dict],
    assumptions: list[str],
    profile: dict,
) -> tuple[list[dict], dict]:
    generated_at = datetime.now(timezone.utc).isoformat()
    handoffs: list[dict] = []
    group_ids: list[str] = []
    for group in implementation_groups:
        stories = group["stories"]
        primary_issue = stories[0]
        secondary_issues = stories[1:]
        branch_name = branch_name_for_group(group, issues, profile)
        repo_surfaces = infer_repo_surfaces(stories, issues, profile)
        handoff = {
            "group_id": group["group_id"],
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "goal": group["goal"],
            "branch_name": branch_name,
            "pr_traceability": {
                "primary_issue": primary_issue,
                "additional_issues": secondary_issues,
                "require_all_keys_in_pr_body": True,
            },
            "entry_criteria": [group["entry_criteria"]],
            "exit_criteria": [group["exit_criteria"]],
            "repo_surfaces": repo_surfaces,
            "implementation_steps": infer_implementation_steps(group, issues),
            "validation_steps": infer_validation_steps(group),
            "risks": [group["reason"]],
            "open_questions": [],
            "source_context": {
                "epic_review_date": generated_at.split("T")[0],
                "implementation_group_reason": group["reason"],
                "group_risk_level": group["risk_level"],
            },
        }
        handoffs.append(handoff)
        group_ids.append(group["group_id"])

    manifest = {
        "epic_key": epic_key,
        "generated_at": generated_at,
        "group_ids": group_ids,
        "manual_review_required": manual_review_required,
        "deferred_changes": deferred_changes,
        "assumptions": assumptions,
    }
    return handoffs, manifest


def build_groups(graph: dict, analysis: dict, repo_evidence: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    issues = issue_map(graph)
    story_confidence = {item["key"]: item["confidence"] for item in analysis.get("stories_with_weak_descriptions", [])}
    story_confidence.update({item["key"]: item["confidence"] for item in analysis.get("epic_misplacement_candidates", [])})

    groups: list[dict] = []
    recommendations: list[dict] = []
    assigned: set[str] = set()
    index = 1

    def add_group(prefix: str, stories: list[str], goal: str, reason: str, risk_level: str, should_split: bool) -> None:
        nonlocal index
        if not stories:
            return
        group_id = group_label(prefix, index)
        index += 1
        groups.append(
            {
                "group_id": group_id,
                "label": prefix.replace("_", " ").title(),
                "stories": stories,
                "goal": goal,
                "reason": reason,
                "suggested_order": len(groups) + 1,
                "parallel_with": [],
                "risk_level": risk_level,
                "should_split_further": should_split,
                "entry_criteria": "Required upstream blockers are resolved and the owning seam is stable.",
                "exit_criteria": "The grouped stories are implemented and verified in one focused PR-sized slice.",
            }
        )
        for story in stories:
            assigned.add(story)
            recommendations.append(
                {
                    "key": story,
                    "execution_mode": "grouped" if len(stories) > 1 else "standalone",
                    "recommended_group_id": group_id,
                    "grouping_reason": reason,
                }
            )

    contract_registry = [
        key for key, issue in issues.items() if categorize_summary(issue.get("summary") or "") & {"contract", "registry"}
    ]
    contract_registry = sorted(contract_registry, key=lambda key: (0 if "contract" in categorize_summary(issues[key]["summary"]) else 1, key))
    if contract_registry:
        should_split = any(story_confidence.get(key) == "low" for key in contract_registry if key in story_confidence)
        add_group(
            "contract_foundation",
            contract_registry[:2],
            "Lock the shared runtime contract and its registry/composition seam.",
            "Contract and registry stories define the execution seam and belong in one small foundation slice.",
            "high",
            should_split,
        )

    adapter_core = [
        key
        for key, issue in issues.items()
        if key not in assigned and categorize_summary(issue.get("summary") or "") & {"runtime", "control", "replay", "scheduler"}
    ]
    if adapter_core:
        adapter_primary = [key for key in adapter_core if "scaffold" not in categorize_summary(issues[key]["summary"])]
        if adapter_primary:
            should_split = any(story_confidence.get(key) == "low" for key in adapter_primary if key in story_confidence)
            add_group(
                "adapter_core",
                adapter_primary[:3],
                "Implement the primary runtime adapter behavior against the shared seam.",
                "These stories share the runtime adapter seam and test harness, so they fit a focused PR-sized batch.",
                "medium",
                should_split,
            )

    scaffolds = [
        key
        for key, issue in issues.items()
        if key not in assigned and categorize_summary(issue.get("summary") or "") & {"scaffold"}
    ]
    for key in scaffolds:
        add_group(
            "scaffold_or_proof",
            [key],
            "Validate abstraction portability with a scaffold or proof adapter.",
            "Scaffold work should stay isolated from the core runtime delivery path.",
            "low" if repo_evidence.get(key, {}).get("status") == "inconclusive" else "medium",
            story_confidence.get(key) == "low",
        )

    hardening = [
        key
        for key, issue in issues.items()
        if key not in assigned and categorize_summary(issue.get("summary") or "") & {"hardening"}
    ]
    for key in hardening:
        add_group(
            "hardening_followup",
            [key],
            "Apply safety or operational hardening after the underlying runtime seam is stable.",
            "Hardening work should stay standalone unless it shares the exact same runtime seam.",
            "medium",
            story_confidence.get(key) == "low",
        )

    remaining = [key for key in sorted(issues) if key not in assigned]
    for key in remaining:
        add_group(
            "consumer_enablement",
            [key],
            "Implement a downstream consumer or follow-on slice once upstream seams are ready.",
            "This story is best handled as an individual PR-sized unit after its blockers land.",
            "medium",
            story_confidence.get(key) == "low",
        )

    groups_by_id = {group["group_id"]: group for group in groups}
    for group in groups:
        parallel_candidates = [
            other["group_id"]
            for other in groups
            if other["group_id"] != group["group_id"]
            and other["suggested_order"] == group["suggested_order"]
        ]
        group["parallel_with"] = parallel_candidates

    for rec in recommendations:
        group = groups_by_id[rec["recommended_group_id"]]
        if group["should_split_further"]:
            rec["execution_mode"] = "standalone"

    return groups, recommendations


def summarize_bucket(item: dict) -> str:
    if item["change_type"] == "create_links":
        return f"Add direct dependency {item['source']} -> {item['target']}."
    if item["change_type"] == "delete_link_ids":
        return f"Review possible deletion of redundant dependency {item['source']} -> {item['target']}."
    if item["change_type"] == "update_descriptions":
        if item.get("manual_direction_required"):
            return f"Need manual direction before normalizing story description for {item['key']}."
        return f"Normalize story description for {item['key']}."
    return f"Add reconciliation comment on {item['key']}."


def main() -> None:
    args = parse_args()
    profile = load_project_profile(repo_root(args.repo_root))
    graph = json.loads(Path(args.graph_json).read_text())
    require_matching_epic(args.epic_key, graph, str(args.graph_json))
    analysis = json.loads(Path(args.analysis_json).read_text())
    require_matching_epic(args.epic_key, analysis, str(args.analysis_json))
    repo = json.loads(Path(args.repo_json).read_text()) if args.repo_json else {}
    if repo:
        require_matching_epic(args.epic_key, repo, str(args.repo_json))
    issues = issue_map(graph)
    repo_evidence = normalize_repo_evidence(repo)

    create_links: list[dict] = []
    delete_link_ids: list[dict] = []
    update_descriptions: list[dict] = []
    create_comments: list[dict] = []
    manual_review_required: list[dict] = []
    deferred_changes: list[dict] = []
    assumptions: list[str] = []
    summary = {
        "safe_to_apply_now": [],
        "needs_review_before_apply": [],
        "deferred_for_manual_decision": [],
    }

    eligible_comment_keys: set[tuple[str, str]] = set()

    for change in analysis.get("likely_reversed_links", []):
        manual_review_required.append(
            {
                "change_type": "reverse_or_replace_link",
                **change,
                "auto_apply_eligible": False,
                "policy_reason": "reversed-link corrections require explicit operator review",
            }
        )
        summary["needs_review_before_apply"].append(
            f"Review likely reversed dependency {change['source']} -> {change['target']}."
        )

    for change in analysis.get("missing_dependency_candidates", []):
        record = mutation_record("create_links", change, repo_evidence)
        create_links.append(record)
        target_bucket = summary["safe_to_apply_now"] if record["auto_apply_eligible"] else summary["needs_review_before_apply"]
        target_bucket.append(summarize_bucket(record))
        if record["confidence"] == "low":
            deferred_changes.append(record)
        elif not record["auto_apply_eligible"]:
            manual_review_required.append(record)
        else:
            eligible_comment_keys.add((record["source"], record["target"]))

    for change in analysis.get("redundant_dependency_candidates", []):
        record = mutation_record("delete_link_ids", change, repo_evidence)
        delete_link_ids.append(record)
        summary["needs_review_before_apply"].append(summarize_bucket(record))
        manual_review_required.append(record)

    for change in analysis.get("soft_coupling_candidates", []):
        manual_review_required.append(
            {
                "change_type": "soft_coupling",
                **change,
                "auto_apply_eligible": False,
                "policy_reason": "soft coupling changes should be reviewed before altering link semantics",
            }
        )
        summary["needs_review_before_apply"].append(
            f"Review whether {change['source']} -> {change['target']} should be downgraded to {change['recommended_type']}."
        )

    for item in analysis.get("stories_needing_description_normalization", []):
        issue = issues.get(item["key"])
        if not issue:
            continue
        description, manual_reason = render_description(issue, item)
        record = mutation_record(
            "update_descriptions",
            {
                **item,
                "key": item["key"],
                "description": description,
                "manual_direction_required": bool(manual_reason),
                "manual_direction_reason": manual_reason,
            },
            repo_evidence,
        )
        if manual_reason:
            record["auto_apply_eligible"] = False
            record["policy_reason"] = "description rewrite needs human direction because story-specific signal is insufficient"
            record["confidence"] = "low"
            record["confidence_reason"] = manual_reason
        update_descriptions.append(record)
        target_bucket = summary["safe_to_apply_now"] if record["auto_apply_eligible"] else summary["needs_review_before_apply"]
        target_bucket.append(summarize_bucket(record))
        if record["confidence"] == "low":
            deferred_changes.append(record)
        elif not record["auto_apply_eligible"]:
            manual_review_required.append(record)
        else:
            eligible_comment_keys.add((record["key"], "description"))

    for key, target in eligible_comment_keys:
        if target == "description":
            comment = mutation_record(
                "create_comments",
                {"key": key, "body": comment_for_description(key), "confidence": "high", "confidence_reason": "comment follows an eligible description normalization", "evidence_sources": ["story_quality"]},
                repo_evidence,
            )
        else:
            change = next(item for item in create_links if item["source"] == key and item["target"] == target)
            comment = mutation_record(
                "create_comments",
                {"key": key, "body": comment_for_link(change), "confidence": change["confidence"], "confidence_reason": "comment follows an eligible dependency correction", "evidence_sources": change["evidence_sources"]},
                repo_evidence,
            )
        comment["auto_apply_eligible"] = True
        comment["policy_reason"] = "comment is paired with an eligible mutation"
        create_comments.append(comment)

    for item in analysis.get("epic_misplacement_candidates", []):
        deferred_changes.append(
            {
                "change_type": "epic_misplacement",
                **item,
                "auto_apply_eligible": False,
                "policy_reason": "epic placement changes stay manual-only",
            }
        )
        summary["deferred_for_manual_decision"].append(f"Review epic placement for {item['key']}.")

    if repo:
        for key, evidence in sorted(repo_evidence.items()):
            if evidence["status"] == "likely_missing_on_main":
                assumptions.append(f"Repo inspection suggests `{key}` may still be missing on main.")
            elif evidence["status"] == "inconclusive":
                assumptions.append(f"Repo inspection was inconclusive for `{key}`.")

    implementation_groups, story_recommendations = build_groups(graph, analysis, repo_evidence)
    implementation_handoffs, epic_handoff_manifest = build_handoffs(
        args.epic_key,
        implementation_groups,
        issues,
        manual_review_required,
        deferred_changes,
        assumptions,
        profile,
    )

    payload = {
        "epic_key": args.epic_key,
        "mode": args.mode,
        "policy": {
            "auto_apply_rule": "apply only high-confidence additive link changes, safe template-completion description rewrites, and paired comments",
            "manual_review_rule": "medium-confidence findings and link deletions remain visible but are not auto-applied",
            "deferred_rule": "low-confidence findings remain deferred for manual decision",
        },
        "create_links": create_links,
        "delete_link_ids": delete_link_ids,
        "update_descriptions": update_descriptions,
        "create_comments": create_comments,
        "manual_review_required": manual_review_required,
        "deferred_changes": deferred_changes,
        "implementation_groups": implementation_groups,
        "implementation_handoffs": implementation_handoffs,
        "epic_handoff_manifest": epic_handoff_manifest,
        "story_recommendations": story_recommendations,
        "summary": summary,
        "assumptions": assumptions,
        "required_story_sections": REQUIRED_STORY_SECTIONS,
    }
    emit_json_and_write_tmp(payload, "change-plan.json")


if __name__ == "__main__":
    main()
