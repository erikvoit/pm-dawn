# Artifact Schema

The skill consumes:
- `.pm-dawn/epics/<epic-key>/slices/<group-id>.md`

Canonical durable outputs:
- `.pm-dawn/epics/<epic-key>/plans/<group-id>.plan.md`
- `.pm-dawn/epics/<epic-key>/packets/<packet-id>.md`

Operational execution output:
- handoff-time compiled packet JSON:
  - `.pm-dawn/epics/<epic-key>/ops/handoffs/<packet-id>.json`

Canonical plan Markdown sections:
- `Slice Identity`
- `Goal`
- `Approved Implementation Approach`
- `Files Likely to Change`
- `Files Explicitly Not to Change`
- `Validation Strategy`
- `Risks and Constraints`
- `Open Questions`
- `Packet Breakdown`
- `Packet Ordering`
- `Source Context`

Canonical packet Markdown sections:
- `Packet ID`
- `Goal`
- `Why This Packet Is Isolated`
- `Depends On`
- `Files to Read`
- `Files to Change`
- `Implementation Steps`
- `Validation Steps`
- `Acceptance Checks`
- `Constraints`
- `Open Questions`
- `Execution Routing`
- `Branch Recommendation`
- `Commit Scope Guidance`
- `Jira Traceability`

Compiled packet JSON fields:
- `schema_version`
- `epic_key`
- `group_id`
- `packet_id`
- `packet_type`
- `risk_class`
- `recommended_executor`
- `routing_notes`
- `primary_issue`
- `secondary_issues`
- `goal`
- `branch_name`
- `pr_traceability`
- `entry_criteria`
- `exit_criteria`
- `repo_surfaces`
- `implementation_steps`
- `validation_steps`
- `open_questions`
- `source_context`
