# PM Dawn Architecture And Boundary

This document records the architectural shape of PM Dawn after the core-library, harness-boundary, and command-surface refactor tracked in `RPVINF-124`.

It is intentionally descriptive rather than aspirational. It explains what PM Dawn owns today, where harness-specific behavior begins, how plan review works between Codex and Pi, and where future ACP convergence could happen without collapsing those scopes now.

## Current Responsibility Split

### Protocol Core

PM Dawn core owns the reusable protocol and repository-local contract that should stay stable across harnesses.

That includes:
- `.pm-dawn` layout and artifact paths
- slice, plan, and packet Markdown parsing
- compiled execution-input generation
- project-profile loading and repo-local defaults
- canonical `epic-slice-implement` command surfaces
- prompt-building rules that define scope, validation, and review expectations
- artifact IO and planning validation helpers
- run metadata and review-monitor state shaping
- Jira key, PR source, PR body, and branch traceability rules that operate only on local PM Dawn data

In practice, this is the seam represented by `pm_dawn_core/` plus the repo-local documents that describe those contracts.

The current inventory of loose skill scripts and their extraction targets is recorded in [script-inventory.md](./script-inventory.md). That inventory is the migration map for `RPVINF-137`: scripts may remain as installed-skill command wrappers, while reusable protocol behavior moves into shared core services.

Current shared service modules include:
- `pm_dawn_core.artifacts`
- `pm_dawn_core.layout`
- `pm_dawn_core.markdown`
- `pm_dawn_core.plan`
- `pm_dawn_core.runs`
- `pm_dawn_core.traceability`
- `pm_dawn_core.runtime`

### Harness Boundary

The harness boundary owns how a concrete agent runtime launches, attaches, steers, and reports status.

That includes:
- selecting `pi` or `opencode`
- provider/model lookup and active-model sanity checks
- server or tmux session management
- runtime-specific attach instructions
- transcript export and session synchronization mechanics

These behaviors live under `epic-slice-implement/scripts/` and are intentionally allowed to vary by harness as long as they honor the shared PM Dawn protocol-core contract.

They must not become imports or hidden dependencies of `pm_dawn_core`.

`RPVINF-134` adds an explicit decision record and scaffold for a future embedded Pi session adapter. That adapter belongs in this harness boundary, not in `pm_dawn_core`. Its shape may borrow from programmable agent-loop designs such as typed sessions, event observations, steering queues, follow-up queues, and execution-environment isolation, but PM Dawn's core contract remains the `.pm-dawn` artifact protocol and plain-Python runtime policy. Until a concrete Pi SDK/session surface is verified, the existing Pi CLI/tmux artifact loop remains the default operational path.

### Repo Documentation Layer

The documentation layer explains the protocol core, harness boundary, lifecycle policy, and command surfaces in a way that future contributors and harness authors can follow without re-deriving the architecture from scripts.

This layer matters because PM Dawn is meant to run from an installed skill directory, not only from this development repo.

### External Client Boundary

The external client boundary owns direct interaction with workflow CLIs that talk to outside services.

That includes:
- Jira graph fetch/apply/verify operations through `acli`
- GitHub PR lookup, creation, update, and verification through `gh`
- Git history inspection used by PR readiness checks

PM Dawn core may own local interpretation of artifact shapes, Jira keys, branch names, PR source payloads, and PR body sections. It should not own live Jira or GitHub client sessions.

## Canonical Command Surface

The current canonical implementation-facing command surface is the `epic-slice-implement/scripts/` entrypoint set, resolved through shared-core command metadata.

Important examples:
- `load_handoff.py`
- `build_opencode_prompt.py`
- `generate_packet_implementation_plan.py`
- `coordinate_plan_review.py`
- `launch_slice_session.py`
- `slice_status.py`
- `mark_slice_pending_review.py`

Compatibility wrappers or harness-specific shortcuts may exist later, but docs and prompts should describe these canonical commands first.

## Codex And Pi Review Protocol

PM Dawn supports a plan-first and review-centered execution loop.

The intended contract is:
- a worker harness, often Pi, may produce a packet-specific `.plan-proposal.md`
- that worker-authored proposal is a draft for review, not the final authority on scope
- Codex or another reviewer reviews and tightens that proposal, recording comments and responses as first-class artifacts
- only explicit acceptance materializes the `.implementation-plan.md` used for implementation
- implementation then starts from the accepted implementation brief plus the packet handoff
- during implementation, the worker may mark `worker.status=pending_review`
- `pending_review` is only a worker claim that the packet is ready for review
- reviewer acceptance remains the authority for completion

The important boundary is that Codex reviews Pi-authored plans rather than silently inheriting or directly mutating worker intent mid-run. The reviewed plan becomes the implementation brief; the worker does not unilaterally redefine the packet.

## ACP Convergence Boundary

Future ACP convergence could happen around:
- runtime wrappers
- shared review or execution orchestration
- more generalized harness abstraction
- replacement or consolidation of some PM Dawn operational scripts

That work is not part of this epic.

For this refactor, PM Dawn remains:
- a portable skill/tooling bundle
- repo-local in its `.pm-dawn` artifacts
- explicit about harness-specific runtime mechanics
- separate from ACP integration or replacement work

The architectural goal is compatibility with future convergence, not premature unification.

## Explicit Out Of Scope For This Epic

The following remain out of scope for `RPVINF-124`:
- implementing ACP integration
- replacing PM Dawn with ACP
- broad workflow redesign beyond the documented refactor seams
- making `.pm-dawn` bootstrap a completed epic deliverable for every future repo shape

`.pm-dawn` bootstrap support exists as part of the shared runtime story, but “fully solved first-run repo bootstrap for every environment” is not the outcome this architecture slice is claiming.

## Migration Rationale

The refactor moved PM Dawn away from a shape that was too entangled with agent-control-plane-era assumptions.

The resulting architecture aims to preserve:
- a reusable protocol core
- a clear harness boundary
- explicit canonical commands
- explicit worker-versus-reviewer responsibilities

That makes future planning and onboarding easier because contributors can now ask:
- Is this protocol-core behavior?
- Is this harness orchestration?
- Is this documentation of the contract?
- Or is this future ACP convergence work?

Those questions should now have stable answers.
