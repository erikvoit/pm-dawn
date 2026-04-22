---
name: packet-implementation-plan
description: Read one approved `.pm-dawn` packet, inspect the current repo seam, and produce a concrete implementation plan before any code edits begin.
---

# Packet Implementation Plan

## Purpose
Use this skill when you need a reviewable implementation plan for one approved `.pm-dawn` packet before attempting to implement it.

This skill is plan-only.

It must:
- read the approved packet Markdown
- inspect the relevant repo surfaces
- produce a concrete implementation plan grounded in repo evidence
- write that plan to `.pm-dawn/epics/<epic>/ops/artifacts/<packet-id>.implementation-plan.md`

It must not:
- edit code
- create or switch branches
- run formatters or code generators that change tracked files
- invent missing routes, endpoints, or backend capability
- claim placeholder behavior is complete behavior

---

## Required Inputs
You need these values before starting:
- `epic_key`
- `packet_id`
- `repo_root`

Resolve the canonical packet path as:
- `.pm-dawn/epics/<epic_key>/packets/<packet_id>.md`

Resolve the output path as:
- `.pm-dawn/epics/<epic_key>/ops/artifacts/<packet_id>.implementation-plan.md`

When you need to refer to the PM Dawn planning entrypoint from instructions or follow-up notes, use the canonical command surface:
- `python "epic-slice-implement/scripts/generate_packet_implementation_plan.py" <epic_key> <group_id> <packet_id> --repo-root .`
- Treat that as the stable PM Dawn command for reviewed packet planning, even if harnesses later add compatibility wrappers around it.

---

## Workflow
1. Read `AGENTS.md`.
2. Read `CONTRIBUTING.md` if present.
3. Read the packet Markdown.
4. Treat the packet as the strict scope boundary.
5. Inspect only the files and adjacent seams needed to plan the packet honestly.

6. **Context Sufficiency Check (required before planning):**
   Confirm you can answer all of the following from inspected repo evidence:
   - What concrete seam or entry point will be modified?
   - Which specific files are most likely to change?
   - What constraints or limitations exist in current code?
   - How will the packet be validated without inventing missing capability?

   If you cannot answer these, inspect more adjacent files before continuing.

7. Produce a deterministic Markdown plan with the required sections below.
8. Write the plan to the required `.pm-dawn` output path, overwriting any prior file.
9. Verify that the file exists at the required output path.
10. If the file does not exist yet, write it and verify again.
11. Do not consider the task complete until the file is confirmed to exist at the required path on disk.
12. Stop. Do not implement anything in this skill.

---

## Planning Rules

### Scope Discipline
- Stay strictly inside the packet’s declared scope.
- Do not widen scope to “improve” unrelated parts of the repo.
- Do not narrow scope such that the packet cannot actually be completed.

### Scope Calibration Check (required)
Before finalizing the plan, explicitly check:
- Are you widening scope beyond the packet to match an imagined ideal design?
- Are you narrowing scope so much that required behavior is not implemented?

If either is true, revise to the smallest honest implementation supported by the repo and packet.

### Evidence-Based Planning
- Prefer concrete repo evidence over inference.
- Every planned change must be traceable to inspected files or seam assumptions with evidence.
- Do not assume helpers, services, endpoints, or abstractions exist without evidence.
- If something is not visible in the repo, do not invent it.

### Handling Missing or Unclear Seams
- If a required seam is missing, record it as a limitation.
- If behavior is unclear, record it as unresolved.
- Do not silently fill gaps with invented implementation.

### Consistency Enforcement
- If the packet conflicts with the repo, report the inconsistency.
- Do not “fix” inconsistencies by expanding scope or inventing behavior.

### Done Conditions
Each done condition must map to either:
- a validation step
- a concrete observable behavior

---

## Required Output Format

Write one Markdown document with exactly these sections:
```md
# <epic_key> / <packet_id> / Implementation Plan

Implementation Summary:
- ...

Seam Assumptions:
- Confirmed from repo: <claim> (file:line or symbol reference)
- Limitation: <constraint> (file:line or symbol reference if applicable)
- Unresolved: <unknown detail and why it cannot be confirmed>

Files To Read:
- ...

Files To Change:
- ...

Planned Changes:
- ...

Planned Todo List:
- ...

Validation:
- ...

Done Conditions:
- ...

Risks or Blockers:
- ...
```

---

## Content Rules

### Implementation Summary
- Short and concrete
- Describe what will be built, not restate the packet

### Seam Assumptions
- Every `Confirmed from repo` item must include concrete evidence:
  - file path + line reference, OR
  - function/class/symbol name
- Do not claim something is confirmed without pointing to where it was observed
- If evidence cannot be provided, classify it as `Unresolved` instead
- `Limitation` items should include evidence where possible
- Do not leave implicit assumptions

### Files To Read
- Include files that justify the implementation approach
- Must include at least one relevant seam (caller, callee, or entry point)
- Files listed here should correspond to evidence cited in `Seam Assumptions`
- Do not pad with broad or irrelevant exploration

### Files To Change
- Only include files you actually expect to modify
- Must be grounded in inspected repo evidence

### Planned Changes
- Group by behavior or subsystem
- Every change must be grounded in inspected repo evidence
- If a change depends on behavior not backed by evidence, it must reference a `Seam Assumptions` entry
- If a change cannot be traced to a concrete seam, remove it or inspect more files

### Planned Todo List
- Required
- 3 to 7 items maximum
- Each item must map to:
  - a file to change, OR
  - a file to read, OR
  - a validation step
- Use concrete implementation steps only
- Do not include:
  - branch creation
  - vague setup work
  - generic research tasks
- Out-of-scope work must go under Risks or Blockers

### Validation
- Include concrete commands, checks, or behaviors
- Must be achievable using existing repo capabilities
- Do not rely on invented tooling or flows

### Risks or Blockers
- Include only real risks, missing seams, or ambiguities
- If none exist, write:
  - `- None`

---

## Output Location

Always write the plan to:

.pm-dawn/epics/<epic_key>/ops/artifacts/<packet_id>.implementation-plan.md

Requirements:
- Overwrite any existing file for the same packet
- Create parent directories if needed
- This file must exist on disk before the task is complete
- Printing the plan in chat/stdout does NOT count as success

---

## Commands

Use shell commands only for reading and inspection. Prefer:
- rg
- sed
- cat
- ls

Only run project-native commands if they do not mutate tracked files.

If writing via shell:
- ensure final file contents exactly match the required Markdown structure

---

## Success Criteria

The skill is successful when:
- The plan file exists at the required path
- The file contents match the required section structure exactly
- All required sections are present
- Files listed are concrete and relevant
- The todo list is scoped and actionable
- Seam assumptions include explicit evidence
- All planned changes are grounded in repo inspection
- No code or tracked files were modified
- The result is not only printed—it exists on disk
