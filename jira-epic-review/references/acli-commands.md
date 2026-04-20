# ACLI Commands

## Authentication

```bash
acli jira auth status
```

If auth is missing and the local keychain token is already set up, use the skill-local helper:

```bash
"$CODEX_HOME/skills/pm-dawn/jira-epic-review/scripts/acli-jira-login"
```

## View a work item

```bash
acli jira workitem view RPVINF-38 --json
acli jira workitem view RPVINF-38 --fields key,summary,status,description
```

## Search child work items

```bash
acli jira workitem search \
  --jql 'parent = RPVINF-38 OR "Epic Link" = RPVINF-38' \
  --fields 'key,summary,status,parent' \
  --json \
  --paginate
```

## List links

```bash
acli jira workitem link list --key RPVINF-61 --json
```

## Create a link

```bash
acli jira workitem link create --out RPVINF-62 --in RPVINF-61 --type Blocks --yes
```

Operational note for this skill:
- if you want `RPVINF-61 blocks RPVINF-62`, the helper plan should still express that as `source=RPVINF-61`, `target=RPVINF-62`
- the apply helper translates that into the CLI's expected `--out/--in` ordering

## Delete a link

```bash
acli jira workitem link delete --id 10136 --yes
```

## Edit description

```bash
acli jira workitem edit --key RPVINF-61 --description-file /tmp/desc.md --yes
```

## Create a comment

```bash
acli jira workitem comment create --key RPVINF-61 --body-file /tmp/comment.md
acli jira workitem comment list --key RPVINF-61 --json
```

## JSON assumptions
- `workitem view --json` returns full fields, including ADF description content.
- `workitem link list --json` returns a compact shape with link IDs and outward or inward keys.
- `workitem comment list --json` is used during verification when the change plan includes expected comments.
- Prefer storing normalized script output rather than parsing ACLI's human-readable text.
