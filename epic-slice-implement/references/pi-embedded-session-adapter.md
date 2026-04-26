# Pi Embedded Session Adapter Decision

`RPVINF-134` evaluates whether PM Dawn should grow an embedded Pi session adapter.

Decision: keep the adapter in the PM Dawn repo for now, behind the `epic-slice-implement`
harness boundary, but do not make embedded Pi sessions the default path yet.

The current implementation is a scaffolded harness contract plus verified Pi RPC
protocol detection. `--runtime embedded` still records fallback capability payloads
and keeps the existing Pi CLI/tmux artifact loop as the operational fallback until
the lifecycle wiring is implemented.

## Design Reference

The Attractor coding-agent-loop spec is the reference shape for the harness layer:

- programmable sessions instead of black-box CLI execution
- typed lifecycle and event observations
- steering and follow-up as distinct queues
- provider-aligned tool behavior rather than a universal tool abstraction
- execution-environment isolation so tool execution policy can change without
  moving provider/session behavior into PM Dawn core

PM Dawn adopts those ideas only at the harness boundary. It does not adopt a new
agent loop inside `pm_dawn_core`, and it does not change the `.pm-dawn` artifact
protocol.

## Adapter Contract

An embedded Pi adapter must provide a small session facade:

- `capabilities`: report whether embedded sessions, event streaming, steering,
  follow-up, and persistent session identity are available.
- `create`: create or resume a Pi session and return stable session identity.
- `submit`: submit an initial packet-planning or implementation prompt.
- `observe`: return typed lifecycle/event observations that PM Dawn can normalize
  into run metadata.
- `steer`: inject guidance after a tool/event boundary when same-session steering
  is supported.
- `follow_up`: queue a new user turn after the current input completes when
  follow-up is supported.
- `close`: close or release the session without deleting PM Dawn artifacts.

The adapter is responsible for provider/session mechanics only. PM Dawn scripts
remain responsible for mapping results to these existing artifacts:

- `.plan-proposal.md`
- `.plan-review.md`
- `.plan-response.md`
- `.plan-review.json`
- `.implementation-plan.md`
- run metadata under `.pm-dawn/epics/<epic-key>/ops/runs/`

## Verified Pi RPC Surface

The local Pi CLI advertises `--mode rpc`, `--session`, `--continue`, `--resume`,
and `--session-dir`. The local Pi RPC docs define a JSONL protocol over
stdin/stdout:

- commands are JSON objects written one per LF-delimited line to stdin
- responses are JSON objects with `type: "response"` and optional request `id`
  correlation
- events are streamed as JSON lines on stdout and do not include request ids
- framing splits on LF only; U+2028 and U+2029 are valid inside JSON strings

The adapter contract should target the subprocess RPC path first, not a Node SDK
helper. That keeps the first working implementation inside PM Dawn's current
plain-Python harness boundary while treating `pi` as an explicit workflow CLI.

Useful RPC commands for PM Dawn:

- `get_state`: returns `sessionId`, `sessionFile`, `sessionName`, streaming state,
  queue mode, and pending message count
- `prompt`: submits the initial slice or packet prompt and returns immediately
  while events stream asynchronously
- `steer`: queues guidance during an active run after the current assistant turn
  finishes tool calls
- `follow_up`: queues a new user turn after the agent finishes
- `set_steering_mode` and `set_follow_up_mode`: control one-at-a-time versus all
  queued delivery
- `switch_session`: loads a session file when PM Dawn has durable metadata
- `set_session_name`: gives PM Dawn sessions a searchable label
- `get_session_stats` and `get_last_assistant_text`: support monitoring and
  compact status output

Useful RPC events for PM Dawn:

- `agent_start` and `agent_end` map to `processing` and completed/idle states
- `turn_start` and `turn_end` describe assistant/tool turns
- `message_start`, `message_update`, and `message_end` provide streaming message
  progress
- `tool_execution_start`, `tool_execution_update`, and `tool_execution_end`
  provide tool-level monitoring
- `queue_update` reports steering/follow-up queue changes

The Pi SDK exposes a richer TypeScript `AgentSession` and `AgentSessionRuntime`
surface, but PM Dawn should not use that as the first implementation path. A
Node/SDK helper remains a future harness-owned option only if the subprocess RPC
protocol cannot support the required lifecycle behavior.

## Capability Semantics

`PiEmbeddedCapabilities.available` means PM Dawn can actually launch and manage
embedded Pi lifecycle behavior now. It does not merely mean the installed `pi`
binary supports RPC.

The packet-01 contract records protocol-level detection separately:

- `protocol`: currently `pi-rpc-jsonl` when the CLI advertises RPC support
- `cli_path`: resolved path to the `pi` binary
- `cli_supports_rpc`: whether `pi --help` advertises RPC mode
- `supports_events`: true for the verified RPC event stream
- `supports_steer`: true for the verified RPC `steer` command
- `supports_follow_up`: true for the verified RPC `follow_up` command
- `supports_persistent_session`: true when CLI help advertises session directory
  and resume/session-file surfaces
- `supports_session_switch`: true when a concrete session file can be passed
- `supports_session_stats`: true for the verified `get_session_stats` command

Until lifecycle wiring lands, PM Dawn may detect `pi-rpc-jsonl` and still return
`available=false` with a fallback reason explaining that the protocol is detected
but the embedded adapter is not wired yet.

## Session Metadata Contract

The embedded snapshot payload should stay bounded and safe to persist in run
metadata. It may include:

- `session_id`: the Pi `sessionId` from `get_state`
- `session_file`: the durable Pi session JSONL path from `get_state`
- `session_dir`: the PM Dawn-owned session directory supplied with
  `--session-dir`
- `protocol`: the detected protocol name
- `process_id`: the local subprocess id when a live process is owned by the
  current PM Dawn command
- `state`: normalized PM Dawn state such as `idle`, `processing`,
  `awaiting_input`, `closed`, or `failed`
- `events`: a recent bounded list of normalized event summaries
- `fallback_reason`: an actionable explanation when embedded behavior is not
  available

Do not persist secrets, API keys, raw credentials, or unbounded transcript/event
payloads in `.pm-dawn` run metadata.

## Current Viability

Embedded Pi protocol viability is proven enough to target `pi --mode rpc` as the
next implementation path. Full PM Dawn lifecycle viability is not wired yet. The
harness module therefore detects RPC support but still reports `available=false`
until create/submit/observe/close behavior is implemented.

`launch_slice_session.py --harness pi --runtime embedded` records the current
snapshot in `embedded_session` metadata and falls back to the current Pi CLI/tmux
artifact loop instead of attempting a partially wired embedded launch.

The next implementation step should wire an opt-in embedded path around the
subprocess RPC protocol. If that path proves insufficient and a helper requires
Node or TypeScript, it must remain a harness-owned optional implementation detail
and must not become a plain-script PM Dawn core dependency.

## Fallback Rules

- Default Pi behavior remains the existing CLI/tmux path in `harness_pi.py`.
- Missing embedded capability must produce an explicit fallback payload, not a
  silent success.
- `slice_status.py` and `sync_slice_session_state.py` surface `embedded_session`
  metadata when run metadata includes it.
- `steer_slice.py` reports artifact-driven revision guidance for Pi embedded runs
  until same-session steering is verified.
- Same-session steering is allowed only when the verified embedded surface supports
  it; otherwise PM Dawn keeps artifact-driven revision relaunch behavior.
- Full event/output data should be available to PM Dawn monitoring when embedded
  mode exists, even if model-facing content is truncated or summarized.
- RPC protocol incompatibility must be reported as a capability/fallback payload,
  not treated as successful embedded launch.

## Core Runtime Boundary

Do not import Pi SDKs, Node helpers, or third-party Python packages from
`pm_dawn_core`.

If PM Dawn later needs a managed runtime wrapper for harness-specific dependencies,
that wrapper should be explicit and shared by the harness entrypoints that need it.
Raw `uv`, `npm`, or local virtualenv assumptions should not leak into individual
plain Python scripts.
