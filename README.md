# PM Dawn

PM Dawn is a Git-backed collection of Codex skills for Jira-driven epic planning, slice refinement, implementation handoff, and PR traceability.

## Included Skills

- `jira-epic-review`: review a Jira epic graph, optionally compare it to the repo, and generate local planning artifacts
- `epic-slice-plan`: turn one reviewed slice into an approved plan and small execution packets
- `epic-slice-implement`: launch and steer packet or slice implementation through the configured harness
- `slice-to-jira`: sync reviewed slice understanding back into Jira story descriptions
- `jira-pr`: prepare, verify, open, and sync PR metadata with strict Jira traceability

## Downstream Agents

- `downstream-agents/packet-implementation-plan/`: a harness-facing planning prompt/spec for producing a concrete implementation plan for one approved packet before coding begins

## Repository Layout

- `*/SKILL.md`: the primary skill instructions
- `*/agents/openai.yaml`: optional agent interface metadata for discoverability and implicit invocation
- `*/scripts/`: helper scripts used by the skill workflows
- `*/references/`: workflow and contract documents used by the skills
- `downstream-agents/`: harness-specific prompts or assets that are part of the PM Dawn workflow, but are not installable Codex skills in this repo

## Notes

- This repo is intended to be installed under `$CODEX_HOME/skills/pm-dawn/`.
- Examples in the skill docs use that installation path explicitly so commands resolve correctly.
- Generated local byproducts such as `__pycache__`, Finder metadata, and Jira review scratch output are ignored.
