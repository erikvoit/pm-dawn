# Jira Description Contract

Every synced Jira story description should use these sections:

## Context
- Why this story exists in the epic.
- One or two concrete sentences only.

## Scope
- What this story is expected to deliver.
- Keep it bounded to the story, even if the slice groups multiple stories together.

## Out of scope
- Adjacent work intentionally left to sibling stories or later slices.
- Use this to keep Jira honest about boundaries.

## Done criteria
- Observable completion conditions.
- Prefer behavior or seam outcomes over implementation trivia.

## Test plan
- What kind of tests or validation should prove the story.
- Keep this at the level of seam coverage, not raw command lines.

## Dependencies
- Briefly state the relevant blocker relationships when they matter for sequencing clarity.
- If dependencies are still uncertain, say so briefly instead of inventing certainty.

## Writing Rules
- Write for posterity, not for the normalization process.
- Keep each story focused on its own role in the slice.
- Use concrete seam language from the reviewed slice artifacts.
- Avoid packet-level detail, branch names, and local-only workflow metadata.
