# PR Body Contract

Canonical title:
- `<PRIMARY-JIRA-KEY>: <concise behavior label>`

Canonical body sections, in order:
1. `What changed`
2. `Jira`
3. `Validation`
4. `Follow-up` only when needed

Required `Jira` block:

```text
Jira
- Primary: RPVINF-61
- Additional: RPVINF-62
```

Rules:
- never paste raw logs
- summarize validation one line per check
- always include all covered Jira keys in the body even if the title contains the primary key
- treat the artifact as the source of truth for Jira coverage
