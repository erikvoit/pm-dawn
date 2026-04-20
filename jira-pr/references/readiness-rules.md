# Readiness Rules

Blocking checks:
- current branch matches the artifact branch recommendation
- at least one branch commit references the primary Jira key
- generated PR body contains a `Jira` block
- generated PR body includes every required Jira key
- generated PR body has a non-empty `Validation` section
- the source artifact is available and parseable

Warnings:
- grouped work has no commit messages referencing secondary Jira keys
- validation is narrower than the repo profile's full-suite command
- existing PR title differs from the generated canonical title

Open/update policy:
- block on any blocking check
- if a PR exists, patch it to canonical generated metadata
- after any mutation, re-verify the live PR body immediately
