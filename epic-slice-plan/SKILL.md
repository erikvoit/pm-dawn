---
name: epic-slice-plan
description: Refine one existing .pm-dawn slice handoff into a decision-complete slice plan and small execution packets. Use when the user wants to take a grouped slice from Jira epic review, ground it in the current repo, produce an approved plan, and split it into packet-sized implementation artifacts without launching coding work.
---

# Epic Slice Plan

## Overview
Use this skill to turn one existing `.pm-dawn` slice handoff into:
- one approved slice plan
- multiple small execution-packet artifacts

This skill plans only. It does not launch `opencode`, create branches, edit repo code, or mutate Jira.

Default behavior:
- mode: `plan`
- input: `.pm-dawn/epics/<epic-key>/slices/<group-id>.md`
- output: Markdown plan artifacts under `.pm-dawn/epics/<epic-key>/plans/` and Markdown packet artifacts under `.pm-dawn/epics/<epic-key>/packets/`
- packet JSON is generated only at execution handoff time
- repo-specific planning heuristics come from `.pm-dawn/project-profile.toml`
- shared parsing, artifact IO, validation, and packet handoff compilation come from `pm_dawn_core` service modules; scripts in this skill are command wrappers over that contract

Use it between:
- `$jira-epic-review`
- `$epic-slice-implement`

## Preconditions
- the slice handoff Markdown already exists under `.pm-dawn/epics/<epic-key>/slices/`
- the repo has `AGENTS.md` and `CONTRIBUTING.md`
- the repo should provide `.pm-dawn/project-profile.toml` so seam classification and validation defaults are project-local instead of hardcoded in the skill
- `.pm-dawn/` is git-ignored or excluded locally

## Inputs
- `epic_key`
- `group_id`
- `repo_root` default `.`
- `mode`: `plan` or `validate`

## Workflow
### Plan
1. Load and validate the slice handoff Markdown.
2. Read `AGENTS.md` and `CONTRIBUTING.md`.
3. Inspect the current repo to identify likely touched files, anchored seams, and unresolved ambiguity.
4. Build an approved slice plan.
5. Split the plan into small execution packets.
6. Write:
   - `.pm-dawn/epics/<epic-key>/plans/<group-id>.plan.md`
   - `.pm-dawn/epics/<epic-key>/packets/<packet-id>.md`
7. Stop. Do not prepare or launch implementation.

### Validate
1. Load the generated plan and packet artifacts.
2. Verify required Markdown sections are present.
3. Verify packet dependencies are coherent.
4. Report whether the slice is ready for packet-level implementation.

## Execution Rules
- Treat the slice handoff as the upstream scope boundary.
- Read `AGENTS.md` and `CONTRIBUTING.md` for branch, commit, and validation policy.
- Prefer narrow packets:
  - one contract change
  - one wiring change
  - one targeted test batch
  - one small compatibility cleanup only when directly required
- Do not widen scope beyond the slice handoff.
- Do not create run metadata. That belongs to `$epic-slice-implement`.
- Do not launch coding work. This skill stops at artifacts.
- Treat Markdown as canonical. Never generate plan or packet JSON during planning.
- Packet JSON exists only at subagent handoff time.
- Keep this skill planning-only: do not add harness launch, session management, or PR/Jira client behavior here.

## Commands
Load a slice handoff:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-plan/scripts/load_slice_handoff.py" \
  RPVINF-38 contract_foundation_1 --repo-root .
```

Inspect slice context:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-plan/scripts/inspect_slice_context.py" \
  RPVINF-38 contract_foundation_1 --repo-root .
```

Build the slice plan:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-plan/scripts/build_slice_plan.py" \
  RPVINF-38 contract_foundation_1 --repo-root .
```

Build execution packets:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-plan/scripts/build_execution_packets.py" \
  RPVINF-38 contract_foundation_1 --repo-root .
```

Generate artifacts:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-plan/scripts/generate_slice_plan_artifacts.py" \
  RPVINF-38 contract_foundation_1 --repo-root .
```

Compile one approved packet Markdown into execution JSON:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-plan/scripts/compile_packet_markdown.py" \
  RPVINF-38 contract_foundation_1 contract_foundation_1__01_contract --repo-root .
```

Validate artifacts:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-plan/scripts/validate_slice_plan.py" \
  RPVINF-38 contract_foundation_1 --repo-root .
```

## References
- [references/artifact-schema.md](./references/artifact-schema.md): plan and packet artifact fields
- [references/packet-rules.md](./references/packet-rules.md): packet sizing, ordering, and packet-type heuristics
- [references/workflow.md](./references/workflow.md): how this skill hands off to `$epic-slice-implement`
