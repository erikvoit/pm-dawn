from __future__ import annotations

import re


def issue_key_re(profile: dict) -> re.Pattern[str]:
    pattern = str(profile.get("project", {}).get("issue_key_pattern", r"\b[A-Z][A-Z0-9]+-\d+\b"))
    return re.compile(pattern)


def jira_keys_in_text(text: str, profile: dict) -> list[str]:
    return sorted(dict.fromkeys(issue_key_re(profile).findall(text)))


def normalize_branch_candidates(branch_name: str, profile: dict) -> set[str]:
    candidates = {branch_name}
    if profile.get("branches", {}).get("allow_codex_prefix", True):
        if branch_name.startswith("codex/"):
            candidates.add(branch_name.removeprefix("codex/"))
        else:
            candidates.add(f"codex/{branch_name}")
    return candidates
