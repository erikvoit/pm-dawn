# Story Template

Use this template when normalizing child work items.

## Required sections
1. `Context`
2. `Scope`
3. `Out of scope`
4. `Acceptance criteria`
5. `Test plan`
6. `Dependencies`

Each section should contain real content, not just a heading. A normalized story is still weak if any section is empty or too thin to guide implementation.
If the available Jira summary, current description, epic context, and dependency graph do not provide enough story-specific signal to fill the template honestly, stop and request manual direction instead of writing boilerplate.

## Template

```markdown
Context:
- Why this story exists now
- Existing repo or Jira state that makes it necessary

Scope:
- Concrete deliverables
- Boundaries and interfaces being added or changed

Out of scope:
- Adjacent work explicitly excluded from this story

Acceptance criteria:
- Observable completion conditions
- Runtime, API, or UX behavior the implementer must satisfy

Test plan:
- Unit, contract, integration, or validation scenarios

Dependencies:
- Explicit upstream blockers
- Important downstream consumers when they affect wording or sequencing
```

## Example guidance
- Interface stories should define contracts, error semantics, and compatibility boundaries.
- Adapter stories should define translation behavior, normalized outputs, and failure handling.
- UI stories should name the backend surfaces they consume and avoid re-specifying backend behavior.
- Hardening stories should spell out the concrete runtime or API behaviors they enforce.
- Never mention the normalization process itself in the final story description. The output should describe the work, not the cleanup.

## Comment policy
- Add a Jira comment when normalization changes the story from vague to handoff-ready.
- Skip comments for trivial wording or formatting edits that do not affect planning clarity.

## Confidence policy
- Missing or empty required sections are high-confidence normalization candidates.
- Thin-but-present sections are medium-confidence and should stay review-first unless the rewrite is clearly template completion.
- If normalizing the story would require inventing new scope, interfaces, or acceptance criteria, defer it instead of auto-applying.
