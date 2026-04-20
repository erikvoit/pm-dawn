# Packet Rules

Default packet types:
- `contract`
- `wiring`
- `tests`
- `cleanup`

Packet sizing rules:
- one clear goal
- one primary validation loop
- minimal touched-file set
- no architecture re-decision
- no cross-packet ambiguity

Preferred ordering:
1. contract
2. wiring
3. tests
4. cleanup

Use `cleanup` only when directly required by the preceding packets.

Path heuristics:
- path-to-packet classification should come from the repo-local `.pm-dawn/project-profile.toml`
- `contract` should represent shared contracts, typed models, or cross-seam interfaces
- `wiring` should represent immediate product/app/provider integration work
- `tests` should stay test-only and should not become the planner's default fallback for a feature slice
- `cleanup` is only for direct follow-up compatibility or scope-tightening changes

Planner guardrail:
- if a feature-oriented slice collapses to only `tests` packets and the project profile disallows that fallback, the planner should fail and report that it could not confidently identify the implementation seam
