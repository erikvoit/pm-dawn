# `.pm-dawn` Lifecycle

Canonical `epic-slice-implement` command surface:

- load/inspect handoff: `python "epic-slice-implement/scripts/load_handoff.py" <epic-key> <group-id> --repo-root .`
- build launch/steer prompt: `python "epic-slice-implement/scripts/build_opencode_prompt.py" <epic-key> <group-id> --repo-root .`
- launch a slice session: `python "epic-slice-implement/scripts/launch_slice_session.py" <epic-key> <group-id> --repo-root .`
- check lifecycle status: `python "epic-slice-implement/scripts/slice_status.py" <epic-key> <group-id> --repo-root .`

Use those canonical commands in docs, prompts, and harness guidance even when a compatibility alias or wrapper also exists.

Use this retention policy for slice artifacts:

- active slice: keep everything
- merged within the last 7 days: optional archive under `.pm-dawn/archive/<epic-key>/<group-id>/`
- merged and reflected in Jira: delete the slice handoff files and run metadata

What to keep:
- `.pm-dawn/epics/<epic-key>/index.md`
- handoffs for slices that are still open

What to archive or delete per merged slice:
- `.pm-dawn/epics/<epic-key>/slices/<group-id>.md`
- `.pm-dawn/epics/<epic-key>/plans/<group-id>.plan.md`
- `.pm-dawn/epics/<epic-key>/packets/<group-id>__*.md`
- `.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.json`
- related `ops/pr/`, `ops/handoffs/`, and `ops/artifacts/` outputs for the same slice

Use archive when:
- the slice merged recently
- you still want short-term auditability
- Jira status or follow-up notes are not fully settled yet

Use delete when:
- the slice is merged
- Jira is updated to reflect the implementation
- the PR and Jira record are now the durable source of truth
