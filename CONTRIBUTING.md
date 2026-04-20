# Contributing

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