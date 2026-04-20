# Linking Rules

Use these rules when creating or deleting work-item links.

## Core rules
- Use `Blocks` only when work on one issue should not start or should not be considered ready until another issue is defined or finished.
- Use `Relates` when the relationship is informative but not a hard sequencing dependency.
- Prefer direct dependencies when the relationship matters for planning clarity, even if a transitive path already exists.
- Treat `Blocks` cycles as errors that should be resolved immediately.
- Track hard blockers, soft couplings, and redundant direct links as separate classes of findings.
- Confidence should stay heuristic and deterministic: strong architecture rules can be `high`, soft/redundant findings usually stay `medium`, and wording-driven graph changes stay `low`.

## Common patterns
- Contract or interface stories should block concrete implementation stories.
- Registry or composition-root stories should block runtime registration or selection stories.
- Runtime control semantics should block operator-control UX.
- Checkpoint and replay semantics should block replay or debug UX.
- Read-only API surfaces usually block client UX that depends on them.
- Hardening stories should usually depend on the underlying runtime or control primitives they enforce.

## Reversed-edge checks
Flag a likely reversed `Blocks` edge when:
- a concrete implementation story blocks an interface-definition story
- a downstream UX story blocks a backend surface it consumes
- a hardening story blocks a runtime primitive that it actually depends on

## Direct vs transitive
Add a direct dependency when:
- the dependent story would look startable without it
- the relationship encodes an important architecture boundary
- the dependency is easy to miss from the transitive graph

Avoid adding a direct dependency when:
- it duplicates obvious sequencing without improving readability
- it creates graph noise without changing planning decisions

Consider a direct dependency redundant when:
- a shorter transitive path already carries the same sequencing information
- the direct edge does not encode an architecture boundary on its own
- removing it would not make the work look more parallel than it really is

Consider a dependency a soft coupling when:
- the downstream story should be aware of the upstream story but can still proceed
- the link is useful for operator context, docs, or release planning but not implementation sequencing
- the current `Blocks` edge is acting more like a reminder than a true prerequisite

## Edge clean-up priorities
1. Remove or reverse wrong `Blocks` links.
2. Add missing direct dependencies that affect sequencing.
3. Downgrade soft couplings from `Blocks` to `Relates`.
4. Verify that no `Blocks` cycle remains.

## Apply policy
- Auto-apply only high-confidence additive `Blocks` changes.
- Keep most deletions manual unless a future policy explicitly upgrades them.
- Surface medium-confidence graph changes for review instead of silently skipping them.
