---
name: jira-epic-review
description: Review a Jira epic and its child work items using ACLI only. Use when the user asks to inspect an epic work graph, improve dependency links, normalize child story descriptions, reconcile Jira planning with the current repo, or apply Jira graph/story cleanup for epic-level planning work.
---

# Jira Epic Review

## Overview
Use this skill to review or normalize a Jira epic's child work graph with ACLI only. It supports two modes:
- `review`: analyze the graph and story quality, optionally inspect the repo, then report findings and write initial local slice artifacts
- `apply`: build a machine-readable change plan, apply only the safe eligible subset, then verify the result

Repo inspection is enabled by default, but it must be purposeful. Inspect the repo when the Jira state may be stale, when shipped code affects sequencing or ticket wording, or when the user explicitly asks to compare Jira with implementation state.

If the repo provides `.pm-dawn/project-profile.toml`, use that profile for branch recommendations and repo-surface hints instead of hardcoded project assumptions.

This skill keeps live Jira work at the ACLI boundary. Shared PM Dawn core services may be used for local `.pm-dawn` artifact paths and Markdown rendering helpers, but `acli` authentication, fetch, apply, and verify operations remain skill-local external client behavior.

## Preconditions
- `acli` is installed and authenticated
- the local ACLI setup is available through the current shell environment
- Jira target is Jira Cloud

Verify auth first:

```bash
acli jira auth status
```

If auth is missing in this environment, use the local helper:

```bash
"$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/acli-jira-login"
```

## Inputs
- `epic_key`: Jira epic key, for example `RPVINF-38`
- `mode`: `review` or `apply`
- `repo_path`: optional path to the repo to inspect, default `.`
- `skip_repo_inspection`: optional flag to force Jira-only analysis

## Workflow
1. Verify ACLI authentication.
2. Fetch the epic and child graph:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/fetch_epic_graph.py" RPVINF-38
```

3. Analyze the graph:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/analyze_epic_graph.py" \
  "$CODEX_HOME/skills/pm-dawn/jira-epic-review/tmp/epic-graph.json"
```

4. Inspect repo context by default unless the user explicitly requests Jira-only analysis or the graph analysis makes it clear repo inspection is unnecessary:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/inspect_repo_context.py" \
  RPVINF-38 \
  --repo-path . \
  --graph-json "$CODEX_HOME/skills/pm-dawn/jira-epic-review/tmp/epic-graph.json" \
  --analysis-json "$CODEX_HOME/skills/pm-dawn/jira-epic-review/tmp/epic-analysis.json"
```

5. Classify findings:
- graph problems
- story-quality problems
- epic-placement problems
- repo-vs-Jira drift when repo inspection is relevant

6. Build a machine-readable change plan from the graph, analysis, and optional repo evidence:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/build_change_plan.py" \
  RPVINF-38 \
  --graph-json "$CODEX_HOME/skills/pm-dawn/jira-epic-review/tmp/epic-graph.json" \
  --analysis-json "$CODEX_HOME/skills/pm-dawn/jira-epic-review/tmp/epic-analysis.json" \
  --repo-json "$CODEX_HOME/skills/pm-dawn/jira-epic-review/tmp/repo-context.json" \
  --mode review
```

7. If `mode=review`, stop after reporting:
- findings ordered by severity
- recommended link edits, split into hard blockers, soft couplings, and redundant links
- recommended story rewrites
- confidence and auto-apply eligibility on every candidate mutation
- PR-sized implementation group recommendations and per-story grouped vs standalone guidance
- implementation handoff data for each PR-sized slice
- repo-backed drift findings when relevant
- unresolved assumptions

8. If `mode=apply`, only proceed when the user explicitly asks for normalization:
- surface the plan first
- create, delete, or adjust only the plan items marked `auto_apply_eligible=true`
- leave medium-confidence and low-confidence changes visible in the plan but unapplied
- rewrite issue descriptions into the standard template only when story quality is actually weak and the rewrite is template-completion safe
- if the story summary, current description, epic context, and dependency position do not provide enough story-specific signal to fill the template honestly, stop and mark the story for manual direction instead of writing generic filler
- add comments only when paired with an eligible link or description change
- verify the final graph against the same plan

## Heuristics
Apply these rules consistently. Read [references/linking-rules.md](./references/linking-rules.md) when link choices are non-obvious.

- contract or interface stories should block implementation stories
- registry or composition stories should block adapter registration and runtime selection, but not all implementation work if coding can proceed safely against the shared contract
- runtime control semantics should block operator-control UX
- checkpoint or replay semantics should block replay or debug UX
- avoid relying only on transitive dependencies when a direct dependency matters for planning clarity
- use `Blocks` only for real sequencing constraints
- use `Relates` for soft coupling or informative awareness
- flag likely reversed `Blocks` edges
- classify soft couplings separately from hard blockers
- classify truly redundant direct links separately from missing or wrong ones
- add heuristic confidence fields to every finding
- treat confidence as deterministic policy input, not a second-opinion model call
- flag `Blocks` cycles as errors
- flag stories with one-line descriptions as not handoff-ready

## Repo Inspection Guidance
Repo inspection is enabled by default, but do not perform rote repo scans on every run. Read [references/repo-inspection-rules.md](./references/repo-inspection-rules.md) when deciding whether to inspect.

Inspect the repo when:
- the user asks whether Jira matches implementation state
- the epic appears stale or ahead/behind code
- ticket readiness depends on existing seams or shipped surfaces
- ambiguity remains after reading Jira alone

Skip repo inspection only when:
- the user explicitly requests Jira-only analysis
- the task is purely graph hygiene with no code-state doubt
- there is no local repo context available

When repo truth-checking is used:
- cite concrete file anchors in the analysis
- distinguish implemented, missing, and inconclusive findings
- use repo evidence to raise or lower finding confidence and grouping confidence
- never edit repo files as part of this skill

## Apply Safety Rules
- never mutate Jira unless the user explicitly asks for `apply`
- prefer additive fixes over destructive graph changes
- if a link must be removed, delete it by link ID and then verify the graph
- keep a machine-readable plan of intended mutations before applying them
- `apply` means safe subset only; it must not execute every planned change
- high-confidence additive blockers and story-specific template-completion description fixes are the only default auto-apply candidates
- medium-confidence changes go to manual review, low-confidence changes are deferred
- comment only when the change affects planning clarity, epic placement, or Jira-vs-repo reconciliation
- for ACLI `Blocks` links, the safe operational rule in this skill is: if you want `A blocks B`, pass `source=A`, `target=B` in the plan and let the helper script translate that to the CLI's expected `--out/--in` ordering

Apply using:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/apply_epic_normalization.py" \
  RPVINF-38 \
  --plan-json /path/to/change-plan.json
```

Then verify:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/verify_epic_graph.py" \
  RPVINF-38 \
  --plan-json /path/to/change-plan.json
```

Generate repo-local handoff artifacts using the reviewed plan:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/generate_handoff_artifacts.py" \
  RPVINF-38 \
  --plan-json "$CODEX_HOME/skills/pm-dawn/jira-epic-review/tmp/change-plan.json" \
  --review-json "$CODEX_HOME/skills/pm-dawn/jira-epic-review/tmp/epic-analysis.json" \
  --repo-root .
```

For normal planning flow, local artifacts are written under `.pm-dawn/epics/<epic-key>/`:
- `index.md` is the epic-level review summary
- `slices/<group-id>.md` are the canonical slice definitions
- `ops/artifacts/` contains raw review or plan snapshots for audit/debug only

The local artifact writes should follow the shared PM Dawn layout and artifact helpers rather than duplicating path or file-IO rules in new scripts.

Behavior by mode:
- `review` does not mutate Jira; it fetches Jira data, analyzes the graph, optionally inspects the repo, and writes local planning artifacts
- `apply` may mutate Jira, but only for safe eligible changes from the generated change plan

Lifecycle policy for generated slice artifacts:
- active slice: keep everything
- merged within the last 7 days: optional archive
- merged and reflected in Jira: delete the slice handoff files and run metadata
- keep the epic index files while the epic is still active

Before generating handoff artifacts, ensure `.pm-dawn/` is ignored by Git:
- prefer a repo-level `.gitignore` entry for `.pm-dawn/`
- if the repo has no `.gitignore` or you should not edit it, use `.git/info/exclude` as a local-only fallback
- if neither ignore path is available, warn clearly that `.pm-dawn/` will appear as untracked Git state

## References
- [references/linking-rules.md](./references/linking-rules.md): `Blocks` vs `Relates`, direct vs transitive dependencies, and common runtime/API/TUI/replay graph rules
- [references/story-template.md](./references/story-template.md): standard issue rewrite template and examples
- [references/repo-inspection-rules.md](./references/repo-inspection-rules.md): when repo inspection is required and how to map code evidence back to Jira planning
- [references/acli-commands.md](./references/acli-commands.md): exact ACLI commands and field usage used by the scripts
