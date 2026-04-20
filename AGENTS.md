# PM Dawn Agent Guide

## Purpose
PM Dawn is a portable skill/tooling bundle intended to run from an installed skill directory such as a Codex skills directory or an OpenCode skills directory. Its workflow scripts should be invokable by multiple agent harnesses without requiring repo-specific Python environment setup.

This document defines the runtime and dependency policy that should guide work in `RPVINF-125` and related refactor stories.

## Runtime Policy

### Core Rule
- Core workflow scripts should be stdlib-only unless there is a compelling reason otherwise.
- Harnesses should be able to invoke PM Dawn tools with plain `python` from the skill directory.
- If any third-party dependency is introduced, it must be behind a well-defined runtime bootstrap layer that every harness can use consistently.

### Why This Exists
- PM Dawn is intended to be installed under a skills directory, not only run inside one specific development repo.
- Different harnesses may call PM Dawn scripts directly from the skill directory and should not need to guess how to bootstrap Python dependencies.
- Hidden Python-library assumptions are much more fragile than explicit CLI-tool assumptions.

## Allowed Dependency Classes

### 1. Python Standard Library
- Preferred for core workflow scripts.
- Safe to assume for portable PM Dawn scripts.
- Should be the default choice unless there is a strong reason to do otherwise.

### 2. Explicit External CLI Dependencies
- Allowed when they are part of the workflow contract rather than hidden Python-library assumptions.
- PM Dawn may explicitly depend on:
  - `python`
  - `acli`
  - `gh`
  - `tmux`
  - `pi`
  - `opencode`
- These dependencies must be treated as required workflow tools, documented clearly, and surfaced in errors when missing.

### 3. Host Repo Dependencies
- PM Dawn should prefer existing repo dependencies when operating on generated repo-local code or artifacts that belong to the host repo.
- PM Dawn should not casually import host-repo Python packages into its own core workflow scripts.
- When generated code belongs to the target repo, that generated code may follow the target repo’s dependency model.

### 4. Third-Party Python Packages for PM Dawn Itself
- Not the default.
- Allowed only when there is a compelling reason that materially improves correctness, maintainability, or portability.
- Must not become an undeclared assumption in plain script entrypoints.
- Must be isolated behind a runtime bootstrap layer that every harness can invoke the same way.

## What Harnesses May Assume
- A PM Dawn core workflow script can be run with plain `python` from the installed PM Dawn skill directory.
- Required external CLI tools are part of the PM Dawn workflow contract and may be assumed only when the specific workflow needs them.
- Harnesses should not have to infer a custom Python environment manager just to run basic PM Dawn scripts.
- Harnesses should not have to guess whether a script needs `uv`, `pip`, or some local virtualenv unless PM Dawn provides a single explicit wrapper for that purpose.

## What Harnesses Must Not Assume
- That third-party Python packages are already installed globally.
- That the host repo’s Python environment is available or appropriate for PM Dawn’s own skill scripts.
- That all PM Dawn scripts may safely be run through an arbitrary dependency manager without a documented PM Dawn runtime contract.

## When Third-Party Python Packages Are Permitted
Third-party Python packages are permitted only when all of the following are true:
- The package provides clear value that is hard to achieve cleanly with the standard library.
- The dependency is justified in the story or packet scope.
- The dependency does not silently become a requirement for plain `python` execution of core workflow scripts.
- The dependency is introduced behind a PM Dawn-owned runtime bootstrap mechanism or wrapper.
- The behavior is documented in this file and in the relevant story or packet notes.

Examples that might justify a third-party dependency:
- Formatting-preserving structured config editing that is too brittle with stdlib alone.
- Strong schema validation that meaningfully reduces workflow breakage across harnesses.
- A compatibility or packaging need that cannot be handled reliably with stdlib primitives.

Examples that do not justify it by default:
- Convenience imports where stdlib is adequate.
- Test-framework preference with no repo-level signal.
- Cosmetic refactors that increase bootstrap complexity.

## Future Runner Wrapper
If PM Dawn eventually needs third-party Python dependencies, the preferred design is a single PM Dawn-owned runner wrapper rather than direct per-script dependency assumptions.

### Desired Shape
- One stable entrypoint or wrapper script, for example:
  - `scripts/run_pm_dawn_python`
  - or `scripts/ensure_pm_dawn_runtime`
- Every harness uses that same wrapper for dependency-managed execution.
- Core scripts remain thin and predictable.
- The wrapper is responsible for:
  - checking runtime prerequisites
  - creating or locating the managed environment
  - invoking Python consistently
  - surfacing clear error messages

### Design Constraints
- Do not make raw `uv` usage an implicit harness requirement.
- If `uv` is used in the future, it should be an implementation detail of the PM Dawn runtime wrapper, not something each harness must know independently.
- The wrapper must behave consistently across Codex, OpenCode, and other harnesses.

## RPVINF-125 Guidance
`RPVINF-125` should establish this runtime contract in the shared PM Dawn core.

That work includes:
- making repo portability a first-class concern
- keeping core workflow scripts portable from the skill directory
- separating explicit CLI requirements from hidden Python-library assumptions
- introducing first-run bootstrap support for `.pm-dawn/`
- defining how a future managed runtime wrapper would work if third-party Python packages ever become necessary

## Working Rule For Contributors
- Prefer stdlib for PM Dawn core scripts.
- Prefer explicit workflow CLIs over hidden Python-library assumptions.
- Prefer existing repo dependencies only for repo-owned generated code, not for PM Dawn’s own core runtime.
- If a third-party Python package seems necessary, stop and document the justification, runtime implications, and harness contract before introducing it.
