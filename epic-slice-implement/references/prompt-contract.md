# Prompt Contract

The launch prompt must always:
- tell the agent to read `AGENTS.md`
- tell the agent to read `CONTRIBUTING.md`
- name the `.pm-dawn` handoff path
- state that the handoff is authoritative
- when present, name the reviewed `.implementation-plan.md` path and explain its role
- when packet negotiation artifacts exist, make it clear that implementation is starting only after explicit reviewer acceptance
- require the worker to stay on the current branch
- forbid branch creation and branch switching
- forbid widening scope
- require validation and an end summary

Launch prompts should include:
- primary and secondary Jira keys
- goal
- implementation steps
- validation steps
- explicit precedence rules:
  - handoff/packet for scope and constraints
  - reviewed implementation plan for concrete implementation approach
  - when the reviewed plan is an `.implementation-plan.md`, explain that it supersedes the worker's earlier draft plan for the same packet
  - stop and report if they conflict
- a short before-edit checklist:
  - read handoff
  - read reviewed plan
  - create a short todo list limited to packet scope
  - stop instead of expanding scope when the todo list would need out-of-scope work
- for implementation runs, an explicit last-step instruction for the worker to mark `pending_review` when it believes the packet is ready for human review
- for reviewed packet implementation briefs, language that makes the reviewer-approved brief authoritative for implementation approach rather than treating the worker's earlier draft as final

Packet-plan runs should:
- require the planning skill to write the `.plan-proposal.md` artifact
- be considered failed if the run returns without that artifact existing on disk
- treat the resulting artifact as review input that Codex or another reviewer can comment on, reject, or accept before implementation launch
- never imply that a worker-authored proposal is already accepted just because the file exists

Steer prompts should include:
- the same handoff path
- the steering message
- an instruction to stop and report conflicts instead of guessing
