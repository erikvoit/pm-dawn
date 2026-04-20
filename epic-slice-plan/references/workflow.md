# Workflow

This skill sits between:
- `$jira-epic-review`
- `$epic-slice-implement`

Upstream:
- `$jira-epic-review` produces slice definitions under `.pm-dawn/epics/<epic-key>/slices/`

This skill:
- grounds one slice in the current repo
- produces an approved slice plan
- splits that plan into execution packets
- labels each packet with routing metadata:
  - `risk_class`
  - `recommended_executor`
  - `routing_notes`
- keeps Markdown as the canonical planning artifact
- stops at artifacts

Downstream:
- `$epic-slice-implement` should consume one compiled packet JSON generated from:
  - `.pm-dawn/epics/<epic-key>/packets/<packet-id>.md`
  - emitted to `.pm-dawn/epics/<epic-key>/ops/handoffs/<packet-id>.json`
