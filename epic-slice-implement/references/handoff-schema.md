# Handoff Schema

The skill consumes:
- `.pm-dawn/epics/<epic-key>/slices/<group-id>.md`
- preferred packet input:
  - canonical packet Markdown:
    - `.pm-dawn/epics/<epic-key>/packets/<packet-id>.md`
  - compiled execution JSON generated only at launch time:
    - `.pm-dawn/epics/<epic-key>/ops/handoffs/<packet-id>.json`
  - packet plan negotiation artifacts:
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-proposal.md`
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-review.md`
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-response.md`
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-review.json`
  - reviewer-accepted implementation brief:
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.implementation-plan.md`

Required execution JSON fields:
- `schema_version`
- `epic_key`
- `group_id`
- `packet_id`
- `primary_issue`
- `secondary_issues`
- `goal`
- `branch_name`
- `packet_type`
- `risk_class`
- `recommended_executor`
- `routing_notes`
- `pr_traceability`
- `entry_criteria`
- `exit_criteria`
- `repo_surfaces`
- `implementation_steps`
- `validation_steps`
- `risks`
- `open_questions`
- `source_context`

The skill writes runtime metadata to:
- `.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.json`

Runtime metadata fields:
- `schema_version`
- `epic_key`
- `group_id`
- `handoff_path`
- `branch_name`
- `harness`
- `runtime_mode`
- `model`
- `model_check.expected_model`
- `model_check.expected_aliases`
- `model_check.active_models`
- `model_check.matches_active_model`
- `model_check.warning`
- `status`
- `phase`
- `completion_state`
- `runtime.server_url`
- `runtime.session_id`
- `runtime.tmux_session`
- `runtime.server_tmux_session`
- `runtime.session_dir`
- `opencode.*` when the selected harness is OpenCode
- `time.created`
- `time.updated`
- `last_action`
- `attach_instructions`
- `worker.status`
- `worker.updated`
- `worker.note`
- `artifacts.plan_md`
- `artifacts.implementation_plan_md`
- `artifacts.result_md`
- `plan_review.status`
- `plan_review.proposal_artifact`
- `plan_review.review_artifact`
- `plan_review.response_artifact`
- `plan_review.implementation_plan_artifact`

Phase/result artifacts live alongside the run metadata:
- `.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.plan.md`
- `.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.result.md`

Fresh implementation runs should consume the approved plan artifact rather than continuing the original planning session transcript.
For packet-first execution, plan review is explicit and artifact-driven:
- worker draft plan proposal:
  - `.plan-proposal.md`
- reviewer comments:
  - `.plan-review.md`
- worker revision/response:
  - `.plan-response.md`
- durable negotiation state:
  - `.plan-review.json`
- accepted implementation brief:
  - `.implementation-plan.md`

**Note for Pi**: The revision loop is artifact-driven. Pi reads `.plan-review.md` and writes `.plan-response.md` for each revision cycle. The accepted implementation brief (`.implementation-plan.md`) is materialized by reviewer acceptance, not worker claim.

Implementation launch for a packet must not begin until `.plan-review.json` records `status=accepted`.
When a packet-specific `.implementation-plan.md` exists and the review state is accepted, implementation runs should consume it as the reviewer-accepted implementation brief.
Packet-first execution is preferred. Whole-slice slice Markdown remains the fallback.
Packet Markdown is canonical; compiled packet JSON is generated at launch time and should not be hand-edited.

Use them as the durable completion signal:
- planning is done when `.plan.md` exists and metadata says `phase=planning`, `completion_state=completed`
- implementation is done when `.result.md` exists and metadata says `phase=implementing`, `completion_state=completed`

Worker-owned review signal:
- `worker.status=pending_review` means the implementation worker believes the packet is ready for review
- this is not equivalent to acceptance or `completion_state=completed`

Review protocol boundary:
- worker-authored packet plan proposals are drafts for reviewer approval
- Codex or another reviewer reviews and tightens that proposal before implementation begins
- reviewer comments and worker responses should be persisted as first-class artifacts, not collapsed into silent overwrite
- the accepted implementation brief is then used alongside the packet handoff
- this schema does not make the worker the final authority on packet scope or acceptance
