# PM Dawn Script Inventory And Extraction Map

This inventory supports `RPVINF-137`. It classifies the loose scripts that still live inside the major PM Dawn skills after the first `pm_dawn_core` extraction.

The goal is not to delete the command surfaces. Most scripts should remain as installed-skill entrypoints, but their reusable PM Dawn protocol behavior should move behind shared core services when doing so preserves plain-`python` execution and the architecture boundary.

## Classification Terms

- `command entrypoint`: a user- or harness-facing CLI surface that should stay as a thin script wrapper.
- `protocol-core candidate`: reusable PM Dawn behavior that should move into `pm_dawn_core` behind a stable service module.
- `harness boundary`: provider, session, process, tmux, server, embedded RPC, or steering mechanics that must stay outside protocol core.
- `external client boundary`: direct interaction with tools such as `acli`, `gh`, or repo search commands; PM Dawn core may own interpretation of local artifacts, but not these client sessions.
- `compatibility shim`: script-local wrapper behavior that may remain temporarily to preserve imports, CLI output, or installed-skill compatibility during extraction.

## Epic Slice Plan Scripts

| Script | Classification | Keep As Entrypoint | Extraction Target | Notes |
| --- | --- | --- | --- | --- |
| `build_execution_packets.py` | protocol-core candidate | Yes | `pm_dawn_core.plan` | Packet derivation, packet ordering, risk classification, and profile-driven seam rules should become shared planning services. |
| `build_slice_plan.py` | protocol-core candidate | Yes | `pm_dawn_core.plan` | Slice plan assembly should be reusable by planning entrypoints and future review tooling. |
| `common.py` | compatibility shim | Temporary | `pm_dawn_core.artifacts`, `pm_dawn_core.layout`, `pm_dawn_core.markdown`, `pm_dawn_core.profile`, `pm_dawn_core.traceability` | This module currently mixes artifact IO, Markdown parsing, repo search, profile loading, and seam classification. |
| `compile_packet_markdown.py` | command entrypoint | Yes | `pm_dawn_core.plan` | CLI should stay; packet Markdown parsing and execution-handoff compilation should become shared services. |
| `generate_slice_plan_artifacts.py` | protocol-core candidate | Yes | `pm_dawn_core.plan`, `pm_dawn_core.markdown` | Rendering and validation of plan/packet Markdown sections should move behind shared helpers. |
| `inspect_slice_context.py` | external client boundary | Yes | `pm_dawn_core.plan` for payload shaping only | Repo inspection and search stay boundary-owned; normalized planning payload shapes can be shared. |
| `load_slice_handoff.py` | command entrypoint | Yes | `pm_dawn_core.plan` | Should become a small wrapper around shared handoff loading and validation. |
| `validate_slice_plan.py` | command entrypoint | Yes | `pm_dawn_core.plan` | Required-section validation and dependency checks should be shared. |

## Epic Slice Implement Scripts

| Script | Classification | Keep As Entrypoint | Extraction Target | Notes |
| --- | --- | --- | --- | --- |
| `build_opencode_prompt.py` | command entrypoint | Yes | `pm_dawn_core.implement` | Prompt construction is already mostly core-owned; script should remain a wrapper. |
| `cleanup_slice_artifacts.py` | command entrypoint | Yes | `pm_dawn_core.artifacts` | Lifecycle target discovery and archive/delete planning can be shared, while the CLI stays explicit. |
| `cleanup_slice_by_name.py` | command entrypoint | Yes | `pm_dawn_core.artifacts` | Name-based artifact discovery should reuse shared layout/artifact helpers. |
| `common.py` | compatibility shim plus harness boundary | Temporary | `pm_dawn_core.artifacts`, `pm_dawn_core.runtime`, harness-boundary module | This module mixes portable IO with tmux/session helpers; extraction must split those responsibilities instead of moving all of it to core. |
| `coordinate_plan_review.py` | command entrypoint | Yes | `pm_dawn_core.implement` | Plan-review state transitions and artifact rules are protocol behavior; CLI stays. |
| `ensure_opencode_server.py` | harness boundary | Yes | None in protocol core | Server detection and startup are provider/session mechanics. |
| `generate_packet_implementation_plan.py` | harness boundary plus command entrypoint | Yes | `pm_dawn_core.implement` for artifact contract only | Harness launch remains boundary-owned; plan artifact paths and accepted-state checks can be shared. |
| `harness_opencode.py` | harness boundary | Yes | None in protocol core | OpenCode process invocation and stdout salvage stay outside core. |
| `harness_pi.py` | harness boundary | Yes | None in protocol core | Pi CLI/tmux planning mechanics stay outside core. |
| `harness_pi_embedded.py` | harness boundary | Yes | None in protocol core | Embedded RPC capability detection, runner lifecycle, event files, and control queues stay outside core. |
| `launch_slice_session.py` | harness boundary plus command entrypoint | Yes | `pm_dawn_core.implement`, `pm_dawn_core.runs` for metadata only | Launch orchestration stays boundary-owned; run metadata construction should be shared. |
| `load_handoff.py` | command entrypoint | Yes | `pm_dawn_core.implement` | Should remain a small wrapper around shared execution-input generation. |
| `mark_slice_pending_review.py` | command entrypoint | Yes | `pm_dawn_core.runs` | Worker-review state writes should use shared run metadata helpers. |
| `migrate_pm_dawn_layout.py` | command entrypoint | Yes | `pm_dawn_core.layout`, `pm_dawn_core.artifacts` | Layout migration planning can reuse shared path contracts; destructive choices stay explicit in the CLI. |
| `record_slice_run.py` | command entrypoint | Yes | `pm_dawn_core.runs` | Run metadata creation and updates should move to shared helpers. |
| `slice_status.py` | command entrypoint | Yes | `pm_dawn_core.runs`, `pm_dawn_core.implement` | Status normalization and review-boundary reporting should be shared. |
| `steer_slice.py` | harness boundary plus command entrypoint | Yes | `pm_dawn_core.runs` for preflight state only | Live steering is harness-specific; pending-review guards and run-state reads can be shared. |
| `sync_slice_session_state.py` | harness boundary plus command entrypoint | Yes | `pm_dawn_core.runs` for normalized status only | Transcript/session sync stays boundary-owned; state normalization and artifact paths can be shared. |

## Jira Epic Review Scripts

| Script | Classification | Keep As Entrypoint | Extraction Target | Notes |
| --- | --- | --- | --- | --- |
| `analyze_epic_graph.py` | protocol-core candidate plus Jira domain logic | Yes | Future `pm_dawn_core.jira_review` or boundary-local service | Graph analysis is reusable, but it is tightly coupled to Jira epic semantics rather than generic core layout. |
| `apply_epic_normalization.py` | external client boundary | Yes | Shared description rendering only | Applying updates through `acli` stays outside core. |
| `build_change_plan.py` | protocol-core candidate plus Jira domain logic | Yes | Future `pm_dawn_core.jira_review` or boundary-local service | Description rendering, dependency normalization, and change-plan shaping are reusable but should not pull `acli` into core. |
| `common.py` | external client boundary plus compatibility shim | Temporary | `pm_dawn_core.profile`, `pm_dawn_core.artifacts` for portable helpers only | Direct `acli` invocation and auth checks stay outside core; profile and artifact helpers should be shared. |
| `fetch_epic_graph.py` | external client boundary | Yes | None in protocol core | Live Jira fetching belongs to the client boundary. |
| `generate_handoff_artifacts.py` | protocol-core candidate | Yes | `pm_dawn_core.artifacts`, `pm_dawn_core.markdown`, `pm_dawn_core.plan` | Handoff/index rendering should reuse shared `.pm-dawn` layout and Markdown helpers. |
| `inspect_repo_context.py` | external client boundary | Yes | None in protocol core | Repo search evidence collection stays boundary-owned. |
| `verify_epic_graph.py` | external client boundary plus protocol-core candidate | Yes | Shared graph validation helpers only | Live fetch stays boundary-owned; local graph validation can be extracted if reused. |

`acli-jira-login` is a shell convenience script and remains an external client boundary artifact.

## Jira PR Scripts

| Script | Classification | Keep As Entrypoint | Extraction Target | Notes |
| --- | --- | --- | --- | --- |
| `build_pr_body.py` | command entrypoint | Yes | `pm_dawn_core.traceability` | PR body construction should use shared Jira key, packet, and artifact rules. |
| `common.py` | compatibility shim | Temporary | `pm_dawn_core.traceability`, `pm_dawn_core.artifacts`, `pm_dawn_core.markdown`, `pm_dawn_core.profile` | This module duplicates project profile loading, issue-key parsing, packet Markdown parsing, and artifact path construction. |
| `find_or_create_pr.py` | external client boundary | Yes | `pm_dawn_core.traceability` for prepared metadata only | Direct `gh pr` lookup/creation stays outside core. |
| `inspect_branch_traceability.py` | command entrypoint | Yes | `pm_dawn_core.traceability` | Branch and commit Jira-key checks should be shared. |
| `jira_pr.py` | command entrypoint and external client boundary | Yes | `pm_dawn_core.traceability` for validation/build inputs only | Orchestration stays in the script; reusable traceability logic moves to core. |
| `load_pr_source.py` | command entrypoint | Yes | `pm_dawn_core.traceability`, `pm_dawn_core.artifacts` | PR source discovery should be shared. |
| `sync_pr_metadata.py` | external client boundary | Yes | `pm_dawn_core.traceability` for body/title generation only | `gh` updates stay outside core. |
| `validate_pr_readiness.py` | command entrypoint | Yes | `pm_dawn_core.traceability` | Readiness checks should share branch, packet, and PR body rules. |
| `verify_pr_traceability.py` | command entrypoint | Yes | `pm_dawn_core.traceability` | Verification should call shared traceability services. |

## Duplicated Helper Families

| Helper Family | Current Homes | Target Home | Boundary Rule |
| --- | --- | --- | --- |
| JSON and text artifact IO | All `common.py` modules plus artifact generators | `pm_dawn_core.artifacts` | Plain file IO belongs in core when it only touches PM Dawn artifacts. |
| `.pm-dawn` path construction | Plan, implement, Jira-review, and PR helpers | `pm_dawn_core.layout` and `pm_dawn_core.artifacts` | Path contracts are protocol core. |
| Markdown section parsing/rendering | `epic-slice-plan/scripts/common.py`, `generate_slice_plan_artifacts.py`, `jira-pr/scripts/common.py`, Jira handoff rendering | `pm_dawn_core.markdown` and `pm_dawn_core.plan` | Shared PM Dawn Markdown contracts belong in core. |
| Project profile loading and validation command lookup | Plan/Jira/PR `common.py` modules | `pm_dawn_core.profile` | Repo-local defaults are protocol core. |
| Jira issue-key extraction and branch traceability | `jira-pr/scripts/common.py`, planning helper heuristics | `pm_dawn_core.traceability` | Parsing and validation rules are core; live Jira/GitHub calls are not. |
| Slice/packet handoff parsing and validation | Plan scripts and implement scripts | `pm_dawn_core.plan` and `pm_dawn_core.implement` | Artifact semantics are core. |
| Plan and packet Markdown rendering/validation | Plan scripts and Jira handoff generation | `pm_dawn_core.plan` | Canonical sections and packet dependency checks are core. |
| Implementation run metadata and review state | Implement scripts | `pm_dawn_core.runs` and `pm_dawn_core.implement` | Run metadata shape is core; live session synchronization is harness boundary. |
| CLI prerequisite checks and shell resolution | Implement scripts and runtime helpers | `pm_dawn_core.runtime` | Shared prerequisite checks belong in runtime; provider invocation remains boundary-owned. |
| tmux/session/provider lifecycle helpers | Implement `common.py`, harness scripts, launch/steer/sync scripts | Harness-boundary module, not protocol core | Process control must stay outside `pm_dawn_core`. |
| `acli` and `gh` invocation helpers | Jira epic review and Jira PR scripts | External client boundary | Core may build inputs and validate outputs; it should not own client sessions. |

## Extraction Order

1. Extract portable helper services: artifact IO, layout wrappers, Markdown section helpers, project profile access, and issue-key/branch parsing.
2. Rewire planning services: slice handoff loading, plan/packet validation, packet rendering, and execution-handoff compilation.
3. Rewire implementation run services: run metadata, status normalization, pending-review state, and artifact path discovery.
4. Rewire Jira epic review and PR traceability services: PM Dawn-owned artifact and traceability rules move to core while `acli` and `gh` calls stay boundary-owned.
5. Add compatibility coverage and documentation updates, then remove only the shims that are proven unnecessary.

## Non-Movement Decisions

- `harness_pi.py`, `harness_pi_embedded.py`, `harness_opencode.py`, `ensure_opencode_server.py`, and live steering/session synchronization mechanics do not move into `pm_dawn_core`.
- Direct `acli` and `gh` invocation does not move into `pm_dawn_core`.
- Skill command entrypoints should remain discoverable unless a later packet provides a documented compatibility replacement.
- No third-party Python dependency is justified by this inventory.
