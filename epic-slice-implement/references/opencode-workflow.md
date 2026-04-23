# Opencode Workflow

Default runtime is `server`:
- ensure `opencode serve` is running in a detached tmux session
- launch slice work against the server
- record server URL, opencode session id, and tmux session names
- prefer `opencode attach` or tmux attach for inspection

Preferred phase split:
- packet-plan run:
  - use the OpenCode `packet-implementation-plan` skill
  - read the packet Markdown
  - write `ops/artifacts/<packet-id>.plan-proposal.md`
  - do not treat the run as successful unless that file exists at the end
  - initialize or update `ops/artifacts/<packet-id>.plan-review.json`
  - treat the written artifact as a worker-authored draft for review, not as self-approving authority
- `planning` run:
  - read the handoff
  - inspect the repo
  - produce the approved implementation plan only
  - write `<group-id>.plan.md`
- `implementing` run:
  - start a fresh session
  - read the compiled execution JSON plus the approved `.plan.md` or reviewed `.implementation-plan.md`
  - implement without carrying the full planning transcript forward

Packet-first execution path:
- packet Markdown is canonical
- compile the selected packet Markdown into `ops/handoffs/<packet-id>.json` immediately before launch
- do not keep packet JSON as a manually maintained companion artifact
- plan negotiation happens through:
  - `ops/artifacts/<packet-id>.plan-proposal.md`
  - `ops/artifacts/<packet-id>.plan-review.md`
  - `ops/artifacts/<packet-id>.plan-response.md`
  - `ops/artifacts/<packet-id>.plan-review.json`
- only when `plan-review.json` records `status=accepted`, use `ops/artifacts/<packet-id>.implementation-plan.md` as the reviewed implementation brief
- for these runs:
  - packet Markdown remains authoritative for scope and constraints
  - reviewed implementation plan remains authoritative for implementation approach
  - if they conflict, the implementation run should stop and report rather than choose silently

Fallback runtime is `tmux-run`:
- run `opencode run` directly inside a dedicated tmux session
- use this only when explicitly requested or when server mode is unavailable

Steering expectations:
- `server` mode supports follow-up prompts against the same session
- `tmux-run` is not treated as reliably steerable; prefer relaunch or server-backed continuation

Completion/result flow:
- do not infer completion from tmux alone
- sync run metadata against `opencode export <session-id>`
- record:
  - `phase`: `planning` or `implementing`
  - `completion_state`: `in_progress`, `completed`, `failed`, `timed_out`
- during implementation, the worker may also write:
  - `worker.status: pending_review`
  - this means “the worker believes the packet is ready for review”
  - it does not mean the packet is accepted
- in the common Codex-Pi flow, Codex reviews Pi-authored proposals, may request changes, and explicitly accepts the brief before implementation launch
- when a phase finishes cleanly, capture the final assistant output into:
  - `<group-id>.plan.md` for planning
  - `<group-id>.result.md` for implementation
