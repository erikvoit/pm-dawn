# Pi Embedded Session Adapter Decision

`RPVINF-134` evaluates whether PM Dawn should grow an embedded Pi session adapter.

Decision: keep the adapter in the PM Dawn repo for now, behind the `epic-slice-implement`
harness boundary, but do not make embedded Pi sessions the default path yet.

The current implementation is a scaffolded harness contract. It makes the desired
shape explicit and keeps the existing Pi CLI/tmux artifact loop as the operational
fallback until a concrete Pi SDK/session surface is verified.

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

## Current Viability

Embedded Pi session viability is not proven in this repo yet. The harness module
therefore reports `available=false` by default and gives a concrete fallback reason.

The next implementation step may wire an opt-in embedded path only after verifying
a Pi SDK/session package or helper process that can support the adapter contract.
If that helper requires Node or TypeScript, it must remain a harness-owned optional
implementation detail and must not become a plain-script PM Dawn core dependency.

## Fallback Rules

- Default Pi behavior remains the existing CLI/tmux path in `harness_pi.py`.
- Missing embedded capability must produce an explicit fallback payload, not a
  silent success.
- Same-session steering is allowed only when the verified embedded surface supports
  it; otherwise PM Dawn keeps artifact-driven revision relaunch behavior.
- Full event/output data should be available to PM Dawn monitoring when embedded
  mode exists, even if model-facing content is truncated or summarized.

## Core Runtime Boundary

Do not import Pi SDKs, Node helpers, or third-party Python packages from
`pm_dawn_core`.

If PM Dawn later needs a managed runtime wrapper for harness-specific dependencies,
that wrapper should be explicit and shared by the harness entrypoints that need it.
Raw `uv`, `npm`, or local virtualenv assumptions should not leak into individual
plain Python scripts.
