---
name: slice-to-jira
description: Sync reviewed .pm-dawn slice planning back into Jira story descriptions. Use when local slice artifacts are more accurate than Jira and you want to update story descriptions on Atlassian Cloud with story-specific Context, Scope, Out of scope, Done criteria, Test plan, and Dependencies derived from reviewed slice boundaries.
---

# Slice To Jira

## Overview
Use this skill after local `.pm-dawn` slice planning to push reviewed slice understanding back into Jira story descriptions.

This skill is for story-description sync, not implementation planning. It should treat the reviewed slice artifacts as the source of truth and update Jira at story granularity.

Read [references/workflow.md](./references/workflow.md) before applying changes.

## When To Use
- Jira stories are weaker or vaguer than the reviewed local slice artifacts.
- An epic has already been grouped into `.pm-dawn` slices and you want better Jira posterity.
- You want to sync story-specific planning sections back to Atlassian Cloud without copying packet detail into Jira.

Do not use this skill:
- before slice planning exists
- to rewrite Jira from packet-level implementation detail
- to do broad graph cleanup first; use `$jira-epic-review` for that

## Inputs
- `epic_key`
- optional `group_id` if syncing only one slice
- `repo_root`, default `.`
- mode:
  - `review`: generate proposed story updates and stop
  - `apply`: update only the reviewed safe subset on Atlassian Cloud

Preferred source order:
1. `.pm-dawn/epics/<epic>/slices/<group-id>.md`
2. `.pm-dawn/epics/<epic>/plans/<group-id>.plan.md` when it adds useful story-level clarity
3. `.pm-dawn/epics/<epic>/index.md` for cross-slice context
4. live Jira issue summaries/descriptions/links

## Workflow
1. Read the relevant slice artifacts and identify which Jira stories they cover.
2. Fetch the current Jira issue descriptions and dependency links for those stories.
3. Build story-specific updates using the slice as the source of truth.
4. Keep the final Jira text at story granularity:
   - `Context`
   - `Scope`
   - `Out of scope`
   - `Done criteria`
   - `Test plan`
   - `Dependencies`
5. Write the review or apply byproducts under:
   - `.pm-dawn/epics/<epic-key>/ops/jira/`
   Recommended filenames:
   - `slice-to-jira-review.md`
   - `slice-to-jira-apply.json`
   - `slice-to-jira-verify.json`
6. In `review` mode:
   - show the proposed updates
   - call out ambiguity or stories that still need human direction
7. In `apply` mode:
   - update only stories whose slice coverage is clear
   - stop on ambiguous stories instead of guessing

## Execution Rules
- Treat reviewed slice artifacts as the source of truth over stale Jira text.
- Summarize at story level only. Do not paste packet text or packet IDs into Jira descriptions unless a short slice note materially helps planning clarity.
- Keep descriptions specific to the story, not the normalization process.
- If multiple stories share one slice, each Jira story still needs its own description focused on that story’s role in the slice.
- Reuse current Jira dependency links when they are still accurate; do not mutate links unless the user explicitly asks.
- If there is not enough story-specific signal to fill the template honestly, stop and report that the story needs manual direction.

## Atlassian Usage
Use the Atlassian MCP tools to:
- read the current issue
- update the description
- optionally add a short comment only when the user asks for visible sync traceability

Prefer updating descriptions directly over adding comments.

## Description Contract
Read [references/description-contract.md](./references/description-contract.md) before drafting updates.

## Safety Rules
- Never mention that the story “was normalized” or “previously lacked sections” in the final Jira description.
- Never copy local packet validation commands into Jira.
- Never describe implementation details that belong to a sibling slice.
- Never apply text that still contains incorrect seam language from another epic or slice.
- Fail closed on ambiguity.

## Output Expectations
In `review` mode, provide:
- covered stories
- proposed description summaries
- any blocked or ambiguous stories
- write a human-readable review artifact to `.pm-dawn/epics/<epic-key>/ops/jira/slice-to-jira-review.md`

In `apply` mode, provide:
- stories updated
- stories skipped and why
- links left unchanged or intentionally untouched
- write any machine-readable apply or verify output under `.pm-dawn/epics/<epic-key>/ops/jira/`
