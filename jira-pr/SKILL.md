---
name: jira-pr
description: Prepare, verify, open, and sync GitHub PR metadata for .pm-dawn-driven work with strict Jira traceability. Use when the user wants to generate a PR title/body from a packet or slice artifact, check branch/commit/PR readiness against Jira keys, open a PR, or patch an existing PR so all covered Jira stories are represented in the live PR body.
---

# Jira PR

This skill reads branch and validation defaults from `.pm-dawn/project-profile.toml` when present, so PR readiness stays project-local instead of assuming one repo's conventions.

## Overview
Use this skill after `$epic-slice-implement` to own PR readiness and Jira traceability.

This skill:
- loads one packet, plan, or whole-slice source
- validates branch and commit traceability
- generates the canonical PR title/body
- opens a PR or patches an existing PR
- verifies that the live PR body contains every required Jira key

PM Dawn-owned parsing, PR source shaping, title/body rendering, artifact paths, and branch-traceability rules live in shared core traceability services. Git history inspection and `gh` PR operations remain external client boundary behavior in this skill.

This skill does not:
- mutate Jira issues or transitions
- implement code
- review epic graphs
- merge PRs

Default policy:
- block PR creation or update when required readiness checks fail
- patch an existing PR to canonical generated metadata when needed
- keep `.pm-dawn` PR artifacts as operational byproducts, not canonical planning artifacts

## Inputs
- `epic_key`
- `group_id`
- optional `packet_id`
- optional `pr_number`
- `mode`: `prepare`, `verify`, `open`, or `sync`
- optional explicit validation lines via repeated `--validation-line`
- optional `--validation-file`

Preferred source order:
1. packet-first:
   - `.pm-dawn/epics/<epic-key>/packets/<packet-id>.md`
   - compiled packet JSON when needed
2. approved plan:
   - `.pm-dawn/epics/<epic-key>/plans/<group-id>.plan.md`
3. slice definition:
   - `.pm-dawn/epics/<epic-key>/slices/<group-id>.md`

## Workflow
### Prepare
1. Load the preferred packet or slice source.
2. Inspect current branch and commit traceability.
3. Gather validation lines from:
   - explicit input first
   - `.pm-dawn` implementation result artifact if present
   - existing PR body as fallback
4. Generate canonical title/body.
5. Write:
   - `.pm-dawn/epics/<epic-key>/ops/pr/<id>.title.txt`
   - `.pm-dawn/epics/<epic-key>/ops/pr/<id>.body.md`
6. Emit readiness and any blocking or warning findings.

### Verify
1. Load the source and current branch state.
2. Locate the live PR by `pr_number` or current branch.
3. Verify:
   - branch matches the source branch recommendation
   - at least one commit references the primary Jira key
   - the live PR body contains the required `Jira` block
   - the live PR body includes all covered Jira keys
   - the live PR body has a non-empty `Validation` section
4. Write `.pm-dawn/epics/<epic-key>/ops/pr/<id>.verify.json`.

### Open
1. Run the full readiness check.
2. Block if required readiness checks fail.
3. If no PR exists for the branch, create one with the generated title/body.
4. If a PR already exists, update it to the generated canonical content.
5. Immediately re-verify the live PR body and write the verification artifact.

### Sync
1. Load the source and existing PR.
2. Patch title/body drift to the generated canonical content.
3. Re-verify the live PR.
4. Write the verification artifact.

## Execution Rules
- Treat the artifact as the source of truth for Jira coverage. Do not infer covered Jira keys from branch name or commit history alone.
- Always require a `Jira` block in the generated PR body:
  - `Primary: <key>`
  - `Additional: <comma list or None>`
- Never paste raw logs in the PR body.
- Summarize validation one line per check.
- Emit warnings for softer issues, but hard-block missing traceability, missing validation, branch mismatch, or unparseable source input.
- Do not move live GitHub API or `gh` command execution into `pm_dawn_core`.

## Commands
Load and normalize a PR source:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-pr/scripts/load_pr_source.py" \
  RPVINF-38 contract_foundation_1 \
  --packet-id contract_foundation_1__01_contract \
  --repo-root .
```

Inspect branch and commit traceability:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-pr/scripts/inspect_branch_traceability.py" \
  RPVINF-38 contract_foundation_1 \
  --packet-id contract_foundation_1__01_contract \
  --repo-root .
```

Prepare title/body artifacts:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-pr/scripts/build_pr_body.py" \
  RPVINF-38 contract_foundation_1 \
  --packet-id contract_foundation_1__01_contract \
  --repo-root . \
  --validation-line "<repo full-suite command> passed locally"
```

Validate PR readiness:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-pr/scripts/validate_pr_readiness.py" \
  RPVINF-38 contract_foundation_1 \
  --packet-id contract_foundation_1__01_contract \
  --repo-root . \
  --validation-line "<repo full-suite command> passed locally"
```

Open or update the PR:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-pr/scripts/jira_pr.py" \
  open \
  RPVINF-38 contract_foundation_1 \
  --packet-id contract_foundation_1__01_contract \
  --repo-root . \
  --validation-line "<repo full-suite command> passed locally"
```

Verify a live PR:

```bash
python "$CODEX_HOME/skills/pm-dawn/jira-pr/scripts/jira_pr.py" \
  verify \
  RPVINF-38 contract_foundation_1 \
  --packet-id contract_foundation_1__01_contract \
  --repo-root .
```

## References
- [references/pr-body-contract.md](./references/pr-body-contract.md): canonical PR title/body shape
- [references/readiness-rules.md](./references/readiness-rules.md): blocking and warning checks
- [references/workflow.md](./references/workflow.md): how this skill fits after `$epic-slice-implement`
