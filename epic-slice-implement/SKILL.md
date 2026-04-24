---
name: epic-slice-implement
description: Launch and steer implementation of one .pm-dawn epic slice through the configured local agent harness. Use when the user wants to consume a .pm-dawn slice or packet artifact, start or monitor a harness-backed implementation session, steer an in-flight slice, or prepare the exact prompt and commands for a slice without launching it.
---

# Epic Slice Implement

## Overview
Use this skill to implement one `.pm-dawn` slice handoff with the configured local agent harness. This skill is operational, not advisory.

Architecture summary:
- protocol-core behavior and command-surface rules come from shared PM Dawn contracts
- harness-specific launch, attach, and session-management behavior stays at the harness boundary
- the durable architecture and ACP boundary are documented in [references/architecture-boundary.md](./references/architecture-boundary.md)

Default behavior:
- mode: `launch`
- runtime: `server`
- handoff source: `.pm-dawn/epics/<epic-key>/slices/<group-id>.md`
- launch phase: `planning` first, then a fresh `implementing` run from the approved `.plan.md`
- project-local branch, validation, harness, and model defaults come from `.pm-dawn/project-profile.toml`

Preferred downstream input is one packet artifact from `$epic-slice-plan`:
- canonical source:
  - `.pm-dawn/epics/<epic-key>/packets/<packet-id>.md`
- compiled at launch time into:
  - `.pm-dawn/epics/<epic-key>/ops/handoffs/<packet-id>.json`
- optional reviewed implementation brief:
  - negotiation artifacts:
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-proposal.md`
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-review.md`
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-response.md`
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.plan-review.json`
  - reviewer-accepted implementation brief:
    - `.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.implementation-plan.md`

Use it only for slice or packet execution and session control. Do not use it for Jira review, Jira normalization, or generic coding work without a `.pm-dawn` handoff or packet artifact.

## Preconditions
- the configured harness CLI is installed and configured
- the selected slice Markdown already exists under `.pm-dawn/epics/<epic-key>/slices/`
- the repo has `AGENTS.md` and `CONTRIBUTING.md`
- the repo should provide `.pm-dawn/project-profile.toml` so validation and branch conventions stay project-local
- the shared runtime contract in `pm_dawn_core/runtime.py` is the authority for shell resolution, env/config overrides, and workflow CLI prerequisite checks

## Inputs
- `epic_key`
- `group_id`
- optional `packet_id` when using packet-first execution
- `repo_root` default `.`
- `mode`: `launch`, `status`, `steer`, or `prepare`
- `runtime`: `server` default, `tmux-run` fallback
- `phase`: `planning` or `implementing`
- optional `approved_plan` for implementation-phase launches
- optional `steering_message`
- optional `harness`; when omitted, resolve from `.pm-dawn/project-profile.toml`
- optional `model`; when omitted, resolve from the selected harness section in `.pm-dawn/project-profile.toml`

Relevant runtime overrides:
- `PM_DAWN_HOME`
- `PM_DAWN_SHELL`
- `PM_DAWN_PROVIDER_TIMEOUT_SECONDS`
- `PM_DAWN_OPENCODE_CONFIG_PATH`
- `PM_DAWN_PI_MODELS_CONFIG_PATH`
- `XDG_CONFIG_HOME`

## Workflows
### Launch
1. Load and validate the preferred packet Markdown, compile it to generated execution JSON only at launch time, or fall back to the whole-slice slice Markdown.
2. Ensure `.pm-dawn/` is protected from Git noise:
   - prefer an existing `.gitignore` rule
   - otherwise use `.git/info/exclude`
3. If the selected harness is `opencode` in server mode, ensure `opencode serve` is running.
4. Build the phase-specific execution prompt.
5. Launch the slice session:
   - `planning`: plan only, no edits or branch switch
   - `implementing`: fresh implementation run from the approved `.plan.md` or reviewer-accepted `.implementation-plan.md`
   - when `--harness` is omitted, resolve the harness from the repo profile:
     - `agent_harness.phase.<phase>` first
     - then `agent_harness.default`
   - when `--model` is omitted, resolve the model from the selected harness section in the repo profile:
     - `<harness>.phase_models.<phase>` first
     - then `<harness>.packet_models.<packet-type>` when a packet id is present
     - then `<harness>.default_model`
6. Record runtime metadata under `.pm-dawn/epics/<epic-key>/ops/runs/<group-id>.json`.
7. Track run phase and completion state in the metadata:
   - `phase`: `planning` or `implementing`
   - `completion_state`: `in_progress`, `completed`, `failed`, or `timed_out`
8. When the worker believes an implementation run is done, it may mark:
   - `worker.status: pending_review`
   This is only a worker claim that the packet is ready for review; it does not mean the packet is accepted or completed.
9. Return attach and status instructions.

### Status
1. Read the run metadata.
2. Report likely state, attach commands, branch name, handoff path, and selected harness.
3. Prefer transcript-derived state over tmux-only heuristics:
   - sync against the actual `opencode` session when the harness is `opencode` and a session id exists
   - surface `phase`, `completion_state`, and any generated `.plan.md` or `.result.md` artifacts
4. For implementation runs, also surface the review boundary explicitly:
   - `implementation_monitor.review_ready=true` means the worker has reached `pending_review`
   - that is the signal to review the result, not to keep steering the worker
   - `completion_state` should remain reviewer-owned until acceptance

### Steer
1. Load the handoff and run metadata.
2. Build a corrective prompt.
3. Send it to the existing session when the harness is `opencode` and runtime mode is `server`.
4. Update run metadata.
5. If the implementation run is already `pending_review`, stop and hand control back to the reviewer instead of sending more steering.

**Note for Pi**: Pi does not support in-session follow-up prompts. A `changes_requested` turn in Pi triggers a fresh bounded revision run that reads the existing `.plan-review.md` and writes a new `.plan-response.md`. Revision is artifact/state monitoring, not a durable server attach/steer surface.

### Sync
1. Read the run metadata and, when supported by the harness, the live session transcript.
2. Update `phase`, `completion_state`, and `status` based on the latest assistant turn.
3. When a phase is complete, capture a repo-local artifact under `.pm-dawn/epics/<epic-key>/ops/runs/`:
   - `<group-id>.plan.md` for planning completion
   - `<group-id>.result.md` for implementation completion
4. Use these artifacts as the durable “done” signal for iterative review and follow-up.
5. For implementation runs, treat `worker.status=pending_review` as a review boundary:
   - write or preserve the `.result.md` artifact
   - expose the implementation monitor state
   - do not silently convert the run to reviewer-completed

For `tmux-run`, do not fake reliable live steering. Report the limitation and prefer relaunching or continuing through a server-backed session.

### Prepare
1. Load the handoff.
2. Build the exact launch prompt and launch command shape.
3. Do not start any session.

### Packet Plan
1. Launch the configured harness for the packet-planning prompt for one packet.
2. Require the packet-specific `.plan-proposal.md` artifact to be written.
3. Treat the step as failed if the OpenCode run returns without creating the artifact file.
4. Review and tighten that artifact through the explicit plan-review loop before implementation launch.

**Note for Pi**: For Pi, the plan proposal/response loop is artifact-driven. Pi reads `.plan-review.md` and writes `.plan-response.md` rather than using conversational steering. The revision loop is bounded and restarts from the existing state, not an in-session follow-up.

### Cleanup
1. Apply the `.pm-dawn` lifecycle policy from [references/pm-dawn-lifecycle.md](./references/pm-dawn-lifecycle.md).
2. Active slice: keep the handoff and run metadata in place.
3. Merged within the last 7 days: optionally archive the slice files and run metadata under `.pm-dawn/archive/<epic-key>/<group-id>/`.
4. Merged and reflected in Jira: delete the slice handoff pair and run metadata, while keeping the epic index files.

## Execution Rules
- Treat the packet Markdown as the canonical source of truth for packet-first execution.
- Treat compiled packet JSON as generated and disposable.
- Prefer `pi` as the default harness when the repo profile selects it, while keeping `opencode` available as a fallback harness.
- Treat `python`, `tmux`, `pi`, and `opencode` as explicit workflow CLIs rather than hidden dependencies.
- Use the shared runtime contract for shell resolution and config discovery:
  - `PM_DAWN_SHELL` then `SHELL` then `zsh`/`bash`/`sh`
  - `PM_DAWN_OPENCODE_CONFIG_PATH` or `XDG_CONFIG_HOME` for OpenCode config
  - `PM_DAWN_PI_MODELS_CONFIG_PATH` for Pi model config
  - `PM_DAWN_PROVIDER_TIMEOUT_SECONDS` for provider sanity-check timeouts
- When a reviewer-accepted `.implementation-plan.md` exists for the packet, treat it as the implementation brief:
  - packet Markdown remains authoritative for scope and constraints
  - reviewed implementation plan remains authoritative for concrete implementation approach
  - if they conflict, the implementation agent must stop and report the conflict
- Do not launch packet implementation when `.plan-review.json` exists but is not `accepted`.
- For implementation runs, the worker may mark the run metadata as `pending_review` when it believes the packet is ready for review.
- Worker-written `pending_review` is not acceptance. Reviewer/Codex completion is still the authority for `completion_state=completed`.
- In the common Codex-Pi flow: Pi authors draft packet implementation plans as `.plan-proposal.md` and `.plan-response.md` artifacts; Codex or another reviewer reviews those drafts and explicitly accepts the `.implementation-plan.md` before coding starts. The reviewer acceptance materializes the canonical implementation brief.
- Whole-slice slice Markdown remains the non-packet fallback.
- Always instruct the implementation agent to read `AGENTS.md` and `CONTRIBUTING.md` before coding.
- Never widen scope beyond the handoff.
- If the handoff is ambiguous, the agent must stop and report the ambiguity instead of inventing requirements.
- Prefer repo-documented `make` or other project-native validation when applicable.
- Do not delete active slice artifacts.
- After merge, only archive or delete the slice-specific files; keep the epic index files unless the entire epic workspace is being retired.
- Do not describe a managed PM Dawn Python runner as if it already exists; the current contract is plain `python` plus explicit workflow CLI prerequisites.

## Commands
Load an execution input:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/load_handoff.py" RPVINF-38 adapter_core_2 --repo-root .
```

Load a packet-derived execution input:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/load_handoff.py" \
  RPVINF-38 contract_foundation_1 \
  --packet-id contract_foundation_1__01_contract \
  --repo-root .
```

Build a launch prompt:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/build_opencode_prompt.py" \
  RPVINF-38 adapter_core_2 \
  --repo-root . \
  --mode launch \
  --phase planning
```

Generate a packet implementation plan and require the artifact to exist:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/generate_packet_implementation_plan.py" \
  RPVINF-39 live_operations_2 live_operations_2__03_tests \
  --repo-root .
```

Accept a packet plan proposal into the canonical implementation brief:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/coordinate_plan_review.py" \
  RPVINF-39 live_operations_2 live_operations_2__03_tests \
  --action accept \
  --repo-root .
```

Ensure the OpenCode server exists:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/ensure_opencode_server.py" --repo-root .
```

Launch a slice:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/launch_slice_session.py" \
  RPVINF-38 adapter_core_2 \
  --repo-root . \
  --runtime server \
  --phase planning
```

Launch implementation from an approved plan:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/launch_slice_session.py" \
  RPVINF-38 adapter_core_2 \
  --repo-root . \
  --runtime server \
  --phase implementing \
  --approved-plan .pm-dawn/epics/RPVINF-38/ops/runs/adapter_core_2.plan.md
```

Launch implementation from a reviewed packet implementation plan:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/launch_slice_session.py" \
  RPVINF-39 live_operations_2 \
  --packet-id live_operations_2__01_wiring \
  --repo-root . \
  --runtime server \
  --phase implementing \
  --approved-plan .pm-dawn/epics/RPVINF-39/ops/artifacts/live_operations_2__01_wiring.implementation-plan.md
```

If `--approved-plan` is omitted for packet execution, the launcher will automatically use:

```text
.pm-dawn/epics/<epic-key>/ops/artifacts/<packet-id>.implementation-plan.md
```

when that file exists and the packet review state is accepted.

Check status:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/slice_status.py" RPVINF-38 adapter_core_2 --repo-root .
```

Mark an implementation run as pending review from the worker side:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/mark_slice_pending_review.py" \
  RPVINF-39 live_operations_2 \
  --repo-root .
```

Sync transcript state and write artifacts:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/sync_slice_session_state.py" \
  RPVINF-38 adapter_core_2 \
  --repo-root . \
  --phase implementing \
  --write-artifacts
```

Steer an in-flight slice:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/steer_slice.py" RPVINF-38 adapter_core_2 "Before continuing, use the repo's make-based validation from CONTRIBUTING.md."
```

Archive a recently merged slice:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/cleanup_slice_artifacts.py" \
  RPVINF-38 scaffold_or_proof_3 \
  --repo-root . \
  --mode archive
```

Archive by slice name only:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/cleanup_slice_by_name.py" \
  scaffold_or_proof_3 \
  --repo-root . \
  --mode archive
```

Delete a merged slice once Jira reflects it:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/cleanup_slice_artifacts.py" \
  RPVINF-38 scaffold_or_proof_3 \
  --repo-root . \
  --mode delete
```

Preview cleanup targets without modifying files:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/cleanup_slice_by_name.py" \
  scaffold_or_proof_3 \
  --repo-root . \
  --mode delete \
  --dry-run
```

Run the one-shot `.pm-dawn` migration:

```bash
python "$CODEX_HOME/skills/pm-dawn/epic-slice-implement/scripts/migrate_pm_dawn_layout.py" \
  --repo-root .
```

## References
- [references/prompt-contract.md](./references/prompt-contract.md): exact prompt requirements and launch vs steer differences
- [references/opencode-workflow.md](./references/opencode-workflow.md): server vs tmux-run behavior and attach/steer expectations
- [references/handoff-schema.md](./references/handoff-schema.md): required slice/packet execution fields and runtime metadata layout
- [references/pm-dawn-lifecycle.md](./references/pm-dawn-lifecycle.md): retention, archive, and deletion policy for merged slices
- [references/architecture-boundary.md](./references/architecture-boundary.md): protocol-core ownership, harness boundary, review protocol, and ACP convergence boundary
