# Repo Inspection Rules

Repo inspection is enabled by default, but should only be used when it helps answer a real planning question.

## Inspect the repo when
- the user asks whether Jira matches implementation state
- an epic appears stale, partially implemented, or ahead of code
- wording or sequencing depends on existing architectural seams
- Jira alone leaves ambiguity that local code can resolve

## Skip repo inspection when
- the user explicitly requests Jira-only analysis
- the task is pure graph hygiene with no code-state uncertainty
- there is no repo available
- the graph analysis already makes the recommendation obvious

## How to inspect
- Prefer non-mutating searches against the local repo.
- Use `rg` or `git grep` to find routes, tests, providers, protocols, or issue keys.
- Inspect `main` branch context when possible, but do not rewrite or change repo files.

## How to report findings
- Cite file anchors when possible.
- Separate:
  - implemented on main
  - likely not implemented
  - inconclusive
- Do not over-claim completion based on partial scaffolding or placeholder interfaces.
- Prefer route, test, provider, protocol, and runtime adapter evidence over docs-only mentions.
- Treat raw grep hits as inputs to an evidence decision, not as completion proof on their own.
- Emit per-issue evidence summaries when possible so the planner can adjust confidence and implementation grouping.
- Use `implemented_on_main` and `likely_missing_on_main` to strengthen planning confidence; use `inconclusive` to lower confidence rather than block planning outright.
