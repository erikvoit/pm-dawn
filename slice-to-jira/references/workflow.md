# Workflow

## Review First
Default to a review pass before applying Jira changes.

Recommended sequence:
1. Read the relevant `.pm-dawn` slice artifacts.
2. Read the current Jira story descriptions for the covered stories.
3. Write a review artifact to `.pm-dawn/epics/<epic>/ops/jira/slice-to-jira-review.md`.
4. Draft proposed story-specific descriptions.
5. Flag any story whose role in the slice is still ambiguous.
6. Apply only the clear subset.

## Good Fits
- Local slice planning is clearly better than the current Jira text.
- Stories were originally created with thin summaries and little acceptance guidance.
- The epic has already been regrouped locally into clearer seams.

## Bad Fits
- The slice plan is still unstable.
- The Jira stories themselves need summary changes, not just description sync.
- The epic graph is still in flux and should be cleaned up first with `$jira-epic-review`.

## Apply Guidance
- Apply only to stories whose scope can be described cleanly from the slice.
- Leave ambiguous stories for human direction.
- Prefer one clean pass after slice review over repeated partial rewrites.
- Keep review/apply byproducts in `.pm-dawn/epics/<epic>/ops/jira/` so the Jira sync work is auditable alongside the slice artifacts.
