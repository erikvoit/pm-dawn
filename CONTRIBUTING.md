# Contributing

PM Dawn changes should preserve three explicit layers:
- protocol-core behavior
- harness-specific orchestration
- documentation of the contract

If a change touches more than one of those layers, call that out directly in the PR and update the matching docs. The durable architecture reference is [epic-slice-implement/references/architecture-boundary.md](./epic-slice-implement/references/architecture-boundary.md).

## Branching
- Use one primary Jira story or task per branch and PR.
- A PR may include additional tightly-coupled Jira stories when they form one small implementation unit that shares the same seam and test surface.
- Branch pattern: `feature/<JIRA-KEY>-<short-slug>` (or `fix/`, `chore/`), where the Jira key is the primary issue for the branch.
- Default to one story per branch, but allow grouped PR-sized slices when splitting the work further would add overhead without improving reviewability or release traceability.
- Do not commit directly to `main`.

## Commits
Use conventional commits to enable automated changelog generation and clear history:
- `feat`: New features
- `fix`: Bug fixes
- `chore`: Maintenance, refactoring, or tooling changes
- `docs`: Documentation updates
- `test`: Adding or modifying tests
- `perf`: Performance improvements
- `refactor`: Code refactoring

Format: `<type>(<optional-scope>): <description>`

Examples:
- `feat(jira-pr): add PR validation for Jira key coverage`
- `fix(branch-traceability): handle multiple Jira keys in commit messages`
- `chore: update contributing guidelines`

## Documentation Expectations

- Keep `README.md` understandable to a new contributor quickly, then let the deeper reference docs carry the detailed contract.
- When command surfaces change, update the canonical examples in docs instead of leaving old wrapper forms behind.
- When review behavior changes, document the worker-versus-reviewer boundary explicitly.
- Do not document ACP convergence as if it is already implemented.
