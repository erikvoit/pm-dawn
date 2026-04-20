# Workflow

This skill sits after:
- `$epic-slice-implement`

Upstream sources:
- packet Markdown and compiled packet JSON from `$epic-slice-plan`
- approved plan Markdown
- slice Markdown

This skill:
- reads the authoritative artifact
- inspects branch and commit traceability
- generates a canonical PR title/body
- opens or updates the live PR
- verifies that the live PR preserves Jira traceability

It does not:
- mutate Jira directly
- merge PRs
- replace implementation validation
