<h1 align="center">🌙 PM Dawn</h1>

<p align="center"><strong>The Local-First Agentic Skill Set. </strong></p>
<p align="center"><em>Plan with frontier models. Execute with local models.</em></p>

<p align="center">
  <img src="https://img.shields.io/badge/build-passing-2ea44f" />
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" />
  <img src="https://img.shields.io/badge/workflow-pm--dawn-black" />
  <img src="https://img.shields.io/badge/agents-frontier%20%2B%20local-purple" />
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" />
</p>

<p align="center">
  <img src="assets/banner.png" width="100%" alt="pm-dawn the agentic skill set set adrift on memory bliss"/>
</p>

## 🧠 Overview

**PM Dawn is a portable skill bundle for turning a Jira epic into:**

- reviewed implementation slices  
- executable packets  
- harness-driven coding runs  
- traceable PR updates  

It defines an **opinionated, repo-local workflow for agent teams**:

> Review → Slice → Plan → Implement → Review → Sync


By breaking an epic into **well-bounded slices and packets**, PM Dawn creates units of work that are small, explicit, and deterministic enough for a **local model to reliably execute**.

This enables a split-brain workflow:

- the **frontier model plans** — structure, sequencing, intent  
- the **local model executes** — implementation, iteration, validation  

PM Dawn sits in the middle as the **project manager**, enforcing boundaries, preserving context, and ensuring planning and execution stay aligned through durable, repo-local artifacts under `.pm-dawn/`.

---

## ⚡ Installation Quick Start

Install PM Dawn into your skills directory, make the downstream agent available to your local harness, then use the workflow below to go from Jira epic to reviewed packet execution.

### Requirements

- `python`
- `git`
- `tmux`
- `gh`
- `acli`
- one implementation harness: `pi` or `opencode`

Environment and config discovery is shared across PM Dawn surfaces. The current runtime contract supports these overrides:

- `PM_DAWN_HOME`
- `PM_DAWN_SHELL`
- `PM_DAWN_PROVIDER_TIMEOUT_SECONDS`
- `PM_DAWN_OPENCODE_CONFIG_PATH`
- `PM_DAWN_PI_MODELS_CONFIG_PATH`
- `XDG_CONFIG_HOME` for OpenCode config discovery

### Install Into Codex Skills

```bash
git clone https://github.com/redpinevalley/pm-dawn.git "$CODEX_HOME/skills/pm-dawn"
cd "$CODEX_HOME/skills/pm-dawn"
make check
```

### Install Into Claude Skills

```bash
git clone https://github.com/redpinevalley/pm-dawn.git "$CLAUDE_HOME/skills/pm-dawn"
cd "$CLAUDE_HOME/skills/pm-dawn"
make check
```

### Make The Downstream Agent Available To Your Local Harness

PM Dawn includes downstream agent assets that are meant to be consumed by the local execution harness, not just by the top-level skill host.

If your local execution loop uses `pi` or `opencode`, make sure the downstream planning/implementation prompt assets are available from the same installed PM Dawn directory:

```text
downstream-agents/packet-implementation-plan/
```

In practice, that means:

- install PM Dawn into the skills directory used by your host agent
- point `pi` or `opencode` at that same installed PM Dawn checkout when they need to read packet-planning or implementation guidance
- do not assume the downstream agent assets exist only in this development repo

### Optional: Manual Bootstrap And Verification

In normal use, the PM Dawn workflow will usually create or migrate `.pm-dawn/` artifacts for you. Run this manually only if you want to verify setup or bootstrap a repo ahead of time.

From a target repo:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/migrate_pm_dawn_layout.py" --repo-root .
```

What this gives you:

- a repo-local `.pm-dawn/` workspace
- default Git protection for `.pm-dawn/` unless you opt out
- canonical PM Dawn command surfaces available from the installed skill directory
- validation that the repo can execute the core PM Dawn workflow

`.pm-dawn/` is durable for workflow state, but usually **ephemeral from a Git perspective**. By default, git should ignore it unless you explicitly decide to version those artifacts.

### Quick Start Workflow

Once PM Dawn is available to your frontier and local agentic harnesses, the happy path looks like this:

1. Use `jira-epic-review` to review a Jira epic and write repo-local slice artifacts under `.pm-dawn/`.
2. Use `epic-slice-plan` to refine that epic output into individual slices.
3. Review those slices with a human in the loop if desired, and decide whether the boundaries and behavior are acceptable before moving on.
4. Use `epic-slice-plan` again to packetize an approved slice into smaller implementation units for local-model execution.
5. Use `epic-slice-implement` from the frontier agent to call the downstream local agent's `packet-implementation-plan` skill so the local harness can draft its own packet implementation plan.
6. Review that packet plan with a human in the loop or continue fully agentically, depending on how much control you want at the review boundary.
7. Launch implementation for the approved packet through `pi` or `opencode`.
8. Observe and iterate on the persisted artifacts under `.pm-dawn/epics/<epic-key>/ops/`, `.pm-dawn/epics/<epic-key>/packets/`, and the related slice directories throughout the run.
9. When a slice is complete, archive or delete the slice-specific artifacts to keep `.pm-dawn/` clean.

See [Example Workflow](#-example-workflow) for a concrete end-to-end packet flow with the relevant skills called out by phase.

In short:

```text
Review epic
  -> refine slices
  -> human review if needed
  -> packetize slice
  -> local packet plan
  -> review brief
  -> implement
  -> review result
  -> archive slice artifacts
```

---

## 📚 Table of Contents

- [🧠 Overview](#-overview)
- [⚡ Installation Quick Start](#-installation-quick-start)
- [🎯 Capability Definition](#-capability-definition)
- [🧬 Terminology](#-terminology)
- [📥 Inputs / 📤 Outputs (Contract)](#-inputs--outputs-contract)
- [⚙️ Execution Model](#️-execution-model)
- [🚀 Example Workflow](#-example-workflow)
- [🧩 Workflow Integration](#-workflow-integration)
- [🧠 Behavioral Rules](#-behavioral-rules)
- [📂 File System Semantics](#-file-system-semantics)
- [🛠️ Development & Extension](#️-development--extension)
- [🧰 Included Skills](#-included-skills)
- [🗺️ Roadmap / Evolution](#️-roadmap--evolution)

---

## 🎯 Capability Definition

### What PM Dawn Does

PM Dawn gives an agent a structured workflow for:

- reviewing a Jira epic and creating `.pm-dawn` planning artifacts
- refining one slice into an approved plan and smaller execution packets
- generating a reviewed packet implementation brief before coding
- launching and steering implementation through `pi` or `opencode`
- tracking review state, packet completion, and PR traceability

### When to Use It

Use PM Dawn when you have:

- a Jira epic or story tree that needs to be reconciled with a real repo
- work that should be split into reviewable implementation slices for a local model to execute
- a plan-first workflow where one agent drafts and another reviews
- a need for durable repo-local artifacts under `.pm-dawn/`

### When Not to Use It

Do not use PM Dawn for:

- generic coding work with no Jira or `.pm-dawn` context
- freeform task management outside the PM Dawn slice / packet workflow
- repo bootstrap claims beyond the current shared runtime story

---

## 🧬 Terminology

### Epic

The Jira epic being reviewed and implemented. PM Dawn stores epic-local artifacts under:

```text
.pm-dawn/epics/<epic-key>/
```

### Slice

A PR-sized unit of work derived from an epic review.

A slice answers:

- what boundary is changing
- which Jira stories are covered together
- what the branch and review unit should be

Canonical slice input:

```text
.pm-dawn/epics/<epic-key>/slices/<group-id>.md
```

### Packet

A smaller execution unit inside a slice.

Packets let PM Dawn break one slice into reviewable steps such as:

- `contract`
- `wiring`
- `tests`
- `cleanup`

Canonical packet input:

```text
.pm-dawn/epics/<epic-key>/packets/<packet-id>.md
```

### Reviewed Implementation Brief

A packet-specific plan written to:

```text
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.implementation-plan.md
```

This starts as review input and becomes the authoritative implementation brief after review. In the common Codex ↔ Pi workflow, Pi may draft it, but Codex reviews and tightens it before implementation starts.

---

## 📥 Inputs / 📤 Outputs (Contract)

### Inputs

PM Dawn primarily consumes:

```text
Jira epic / story graph
.pm-dawn/epics/<epic-key>/slices/<group-id>.md
.pm-dawn/epics/<epic-key>/packets/<packet-id>.md
.pm-dawn/project-profile.toml
CLI args such as <epic-key> <group-id> --packet-id ... --repo-root .
```

Required inputs depend on the phase:

- **Epic review** needs Jira access plus a repo root.
- **Slice planning** needs an existing slice Markdown handoff.
- **Packet planning** needs a packet Markdown file.
- **Implementation launch** needs either a slice handoff or a packet plus any reviewer-accepted implementation brief.

Assumptions:

- PM Dawn runs from an installed skill directory such as `$CODEX_HOME/skills/pm-dawn/`.
- Core workflow scripts are runnable with plain `python`.
- External CLIs such as `tmux`, `pi`, `opencode`, `gh`, and `acli` are explicit workflow dependencies, not hidden Python package assumptions.
- Environment/config lookup and CLI prerequisite behavior come from the shared runtime contract in `pm_dawn_core/runtime.py`.

### Outputs

PM Dawn writes deterministic repo-local artifacts under `.pm-dawn/`.

Typical outputs include:

```text
.pm-dawn/epics/<epic-key>/slices/<group-id>.md
.pm-dawn/epics/<epic-key>/plans/<group-id>.plan.md
.pm-dawn/epics/<epic-key>/packets/<packet-id>.md
.pm-dawn/epics/<epic-key>/ops/handoffs/<packet-id>.json
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-proposal.md
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-review.md
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-response.md
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-review.json
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.implementation-plan.md
.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.json
.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.plan.md
.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.result.md
.pm-dawn/epics/<epic-key>/ops/pr/<group-id>.body.md
```

Determinism expectations:

- Packet Markdown is canonical.
- Compiled packet JSON is generated at launch time and should be treated as disposable.
- Packet plan negotiation artifacts are durable review history.
- Reviewer-accepted implementation briefs are durable execution input.
- Run metadata and captured plan / result artifacts are the durable execution record.

---

## ⚙️ Execution Model

PM Dawn is invoked through skill-local Python entrypoints.

Canonical command surface:

```bash
python "epic-slice-implement/scripts/load_handoff.py" <epic-key> <group-id> --repo-root .
python "epic-slice-implement/scripts/build_opencode_prompt.py" <epic-key> <group-id> --repo-root .
python "epic-slice-implement/scripts/generate_packet_implementation_plan.py" <epic-key> <group-id> <packet-id> --repo-root .
python "epic-slice-implement/scripts/coordinate_plan_review.py" <epic-key> <group-id> <packet-id> --action accept --repo-root .
python "epic-slice-implement/scripts/launch_slice_session.py" <epic-key> <group-id> --repo-root .
python "epic-slice-implement/scripts/slice_status.py" <epic-key> <group-id> --repo-root .
```

Expected environment:

- plain `python`
- repo root available via `--repo-root`
- `.pm-dawn/project-profile.toml` when repo-local defaults matter
- harness CLI installed for the chosen runtime (`pi` or `opencode`)
- Pi embedded sessions are an opt-in runtime via `--harness pi --runtime embedded`; PM Dawn uses Pi's RPC JSONL mode when available and falls back to the existing Pi CLI/tmux artifact loop when capability checks fail

Shared runtime behavior:

- PM Dawn resolves shell execution through `PM_DAWN_SHELL`, then `SHELL`, then `zsh`, `bash`, and `sh`
- OpenCode config is discovered from `PM_DAWN_OPENCODE_CONFIG_PATH`, then `XDG_CONFIG_HOME`, then `~/.config/opencode/opencode.json`
- Pi model config is discovered from `PM_DAWN_PI_MODELS_CONFIG_PATH`, then `~/.pi/agent/models.json`
- `PM_DAWN_HOME` can override the home-directory base for PM Dawn-owned lookups
- `PM_DAWN_PROVIDER_TIMEOUT_SECONDS` controls the provider model sanity-check timeout
- missing workflow CLIs fail as explicit PM Dawn prerequisite errors rather than as hidden process errors

Idempotency and overwrite behavior:

- generated plan and packet artifacts overwrite prior versions when regenerated
- packet plan proposals, reviews, and responses overwrite their own prior draft for the same packet
- reviewer acceptance copies the accepted source into the canonical `.implementation-plan.md`
- packet JSON is regenerated at launch time
- run metadata is updated in place

Important side effects:

- PM Dawn writes and updates `.pm-dawn/` artifacts
- migration and bootstrap flows default to adding `.pm-dawn/` to `.gitignore`
- launch flows may create tmux sessions and harness runtime state
- Pi embedded sessions add bounded `embedded_session` metadata and PM Dawn-owned RPC state files under the run session directory without changing `.pm-dawn` proposal/review/response/acceptance artifacts
- implementation workers may mark `worker.status=pending_review`
- `pending_review` is not acceptance; reviewer completion remains separate
- PM Dawn does not require a managed Python runner wrapper today; plain `python` is still the supported execution path for core workflow scripts

---

## 🚀 Example Workflow

In normal use, the agent will usually invoke these Python entrypoints for you through the relevant PM Dawn skill. The commands below are the concrete command surfaces behind that workflow, and are most useful when you want to inspect, debug, or manually drive a phase yourself.

### Example Invocation

Refine a reviewed slice into packets with `epic-slice-plan`:

```bash
python "epic-slice-plan/scripts/generate_slice_plan_artifacts.py" \
  RPVINF-124 consumer_enablement_6 \
  --repo-root .
```

Generate a packet implementation draft with `epic-slice-implement` calling the downstream `packet-implementation-plan` skill:

```bash
python "epic-slice-implement/scripts/generate_packet_implementation_plan.py" \
  RPVINF-124 consumer_enablement_6 consumer_enablement_6__01_contract \
  --repo-root .
```

Accept that proposal into the canonical implementation brief:

```bash
python "epic-slice-implement/scripts/coordinate_plan_review.py" \
  RPVINF-124 consumer_enablement_6 consumer_enablement_6__01_contract \
  --action accept \
  --repo-root .
```

Launch implementation from the accepted brief with `epic-slice-implement`:

```bash
python "epic-slice-implement/scripts/launch_slice_session.py" \
  RPVINF-124 consumer_enablement_6 \
  --packet-id consumer_enablement_6__01_contract \
  --repo-root . \
  --phase implementing
```

### Example Input

```text
.pm-dawn/epics/RPVINF-124/index.md
.pm-dawn/epics/RPVINF-124/slices/consumer_enablement_6.md
.pm-dawn/epics/RPVINF-124/packets/consumer_enablement_6__01_contract.md
```

### Example Output

```text
.pm-dawn/epics/RPVINF-124/plans/consumer_enablement_6.plan.md
.pm-dawn/epics/RPVINF-124/packets/consumer_enablement_6__01_contract.md
.pm-dawn/epics/RPVINF-124/ops/artifacts/consumer_enablement_6__01_contract.plan-proposal.md
.pm-dawn/epics/RPVINF-124/ops/artifacts/consumer_enablement_6__01_contract.plan-review.json
.pm-dawn/epics/RPVINF-124/ops/artifacts/consumer_enablement_6__01_contract.implementation-plan.md
.pm-dawn/epics/RPVINF-124/ops/runs/consumer_enablement_6.json
```

### Phase Map

- Epic review phase: `jira-epic-review`
- Slice refinement and packetization phase: `epic-slice-plan`
- Packet plan draft phase: `epic-slice-implement` using the downstream `packet-implementation-plan` skill
- Implementation phase: `epic-slice-implement`
- PR and Jira sync phase: `jira-pr` and `slice-to-jira`

---

## 🧩 Workflow Integration

### Happy Path

1. Create or identify a Jira epic.
2. Review that epic into repo-local slice handoffs.
3. Turn one slice into an approved slice plan plus packets.
4. Generate a worker-authored plan proposal for one packet.
5. Review, comment on, and accept that proposal into the implementation brief.
6. Launch implementation through the chosen harness.
7. Review the implementation result.
8. Update PR metadata and sync Jira when the packet or slice is accepted.

### Upstream Producers

#### `jira-epic-review`

- reviews the Jira graph
- writes epic-local slice handoffs and index artifacts

#### `epic-slice-plan`

- consumes one reviewed slice
- writes the slice plan and packet artifacts

### Downstream Consumers

#### `epic-slice-implement`

- consumes the slice or packet
- launches planning and implementation runs

#### `jira-pr`

- consumes the slice / packet / Jira traceability state
- prepares and syncs the PR

#### `slice-to-jira`

- pushes refined local slice understanding back into Jira story descriptions

### Pipeline Position

PM Dawn sits in the middle of the agent workflow:

```text
Jira epic
  -> jira-epic-review
  -> slice handoff
  -> epic-slice-plan
  -> packet
  -> packet-implementation-plan
  -> plan proposal / review / response / acceptance
  -> epic-slice-implement
  -> review
  -> jira-pr / slice-to-jira
```

---

## 🧠 Behavioral Rules (Agent Guidance)

### Agents Must

- treat slice and packet artifacts as the scope boundary
- prefer packet-first execution when packets exist
- treat reviewed implementation briefs as authoritative for implementation approach
- treat packet plan negotiation artifacts as the review loop, not as disposable side chatter
- keep `.pm-dawn` artifacts repo-local and traceable
- use the canonical command surface in docs, prompts, and workflow guidance
- validate work with the repo’s native checks

### Agents Must Not

- widen scope beyond the slice or packet
- treat a worker-authored draft plan as self-approved
- start packet implementation before the plan-review state is explicitly accepted
- treat `pending_review` as acceptance
- hand-edit compiled packet JSON as a maintained artifact
- silently collapse protocol-core behavior and harness-specific behavior into one undocumented seam

### Common Failure Modes

- empty or low-signal slice handoffs that do not identify the real repo seam
- packetization that follows file heuristics instead of the actual architectural boundary
- worker plans being mistaken for approved implementation briefs
- docs drifting away from the canonical command surface

### Validation Expectations

For this repo, the default full check is:

```bash
make check
```

That currently runs:

```bash
python -m py_compile pm_dawn_core/*.py epic-slice-plan/scripts/*.py epic-slice-implement/scripts/*.py jira-epic-review/scripts/*.py jira-pr/scripts/*.py
python -m unittest discover tests
```

---

## 📂 File System Semantics

Required directories:

```text
.pm-dawn/epics/
.pm-dawn/archive/
.pm-dawn/tmp/
```

Important path conventions:

```text
.pm-dawn/epics/<epic-key>/index.md
.pm-dawn/epics/<epic-key>/slices/<group-id>.md
.pm-dawn/epics/<epic-key>/plans/<group-id>.plan.md
.pm-dawn/epics/<epic-key>/packets/<packet-id>.md
.pm-dawn/epics/<epic-key>/ops/handoffs/<packet-id>.json
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-proposal.md
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-review.md
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-response.md
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-review.json
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.implementation-plan.md
.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.json
.pm-dawn/epics/<epic-key>/ops/pr/<group-id>.body.md
```

Naming conventions:

- `group_id` identifies the slice
- `packet_id` is `<group-id>__<ordinal>_<type>`
- branch convention is usually `feature/<JIRA-KEY>-<slug>`

Overwrite semantics:

- plan and packet generation overwrite existing artifacts for the same slice
- implementation-plan generation overwrites the prior draft for the same packet
- run metadata is updated in place
- archive / delete flows should only touch slice-specific artifacts
- `.pm-dawn/` should usually be ignored in Git; opt out only when you intentionally want those artifacts checked in

---

## 🛠️ Development & Extension

### Modify the Workflow

- update the relevant `SKILL.md` file when behavior changes
- update the matching `references/*.md` contract doc when boundaries or expectations change
- keep `README.md` focused on the top-level workflow contract, not script internals

### Test Changes

```bash
make check
python -m unittest discover tests
```

### Add a Variant

If you add:

- a new harness flow
- a new command surface
- a new planning or review stage

then update:

- shared architecture docs
- the relevant skill doc
- canonical command examples
- tests or smoke checks that enforce the new contract

---

## Included Skills

- `jira-epic-review` — review a Jira epic graph, optionally compare it to the repo, and generate local planning artifacts
- `epic-slice-plan` — turn one reviewed slice into an approved plan and small execution packets
- `epic-slice-implement` — launch and steer packet or slice implementation through the configured harness
- `slice-to-jira` — sync reviewed slice understanding back into Jira story descriptions
- `jira-pr` — prepare, verify, open, and sync PR metadata with strict Jira traceability

---

## 🗺️ Roadmap / Evolution

Planned or likely follow-on work:

- stronger shared runtime prerequisite detection across all PM Dawn surfaces
- better first-run bootstrap ergonomics for new repo shapes
- more explicit harness wrappers if third-party Python runtime management ever becomes necessary

Known limitations:

- PM Dawn still expects explicit workflow CLIs for some flows
- the planning pipeline sometimes still needs manual packetization when story signal is weak

---

## License

MIT License

Copyright (c) 2026 Erik Voit

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
