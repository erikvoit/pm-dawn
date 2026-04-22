#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pm_dawn_core.layout import (
    compiled_packet_json_path,
    implementation_plan_artifact_path,
    legacy_opencode_plan_artifact_path,
    packet_markdown_path,
    reviewed_plan_artifact_path,
    run_artifact_path,
    run_metadata_path,
    slice_markdown_path,
)
from pm_dawn_core.markdown import bullet_values, parse_markdown_sections, single_bullet
from pm_dawn_core.profile import (
    load_project_profile as load_core_project_profile,
    make_default_profile,
    repo_root,
)

REQUIRED_HANDOFF_FIELDS = [
    "schema_version",
    "epic_key",
    "group_id",
    "primary_issue",
    "secondary_issues",
    "goal",
    "branch_name",
    "pr_traceability",
    "entry_criteria",
    "exit_criteria",
    "repo_surfaces",
    "implementation_steps",
    "validation_steps",
    "risks",
    "open_questions",
    "source_context",
]

DEFAULT_PROJECT_PROFILE: dict = make_default_profile(
    {
        "agent_harness": {
            "default": "opencode",
        },
        "pi": {
            "default_model": "qwen/qwen3-coder-next-q6k",
        },
        "opencode": {
            "default_model": "llama/qwen/qwen3-coder-next",
        },
    }
)


def emit_json(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_project_profile(root: Path) -> dict:
    return load_core_project_profile(root, DEFAULT_PROJECT_PROFILE)


def full_suite_command(root: Path) -> str:
    profile = load_project_profile(root)
    return str(profile.get("validation", {}).get("full_suite_command", "make check"))


def packet_type_from_id(packet_id: str | None) -> str | None:
    if not packet_id:
        return None
    if "__" not in packet_id:
        return None
    suffix = packet_id.rsplit("__", 1)[-1]
    if "_" not in suffix:
        return None
    return suffix.split("_", 1)[1]


def resolve_agent_harness(
    root: Path,
    *,
    explicit_harness: str | None = None,
    phase: str | None = None,
) -> str:
    profile = load_project_profile(root)
    harness_config = profile.get("agent_harness", {})
    aliases = harness_config.get("aliases", {})

    def resolve_alias(value: str | None) -> str | None:
        if value is None:
            return None
        return str(aliases.get(value, value))

    if explicit_harness:
        return resolve_alias(explicit_harness) or explicit_harness

    phase_harnesses = harness_config.get("phase", {})
    if phase:
        phase_harness = resolve_alias(phase_harnesses.get(phase))
        if phase_harness:
            return phase_harness

    default_harness = resolve_alias(harness_config.get("default"))
    if default_harness:
        return default_harness
    return "opencode"


def resolve_harness_model(
    root: Path,
    *,
    harness: str,
    explicit_model: str | None = None,
    phase: str | None = None,
    packet_id: str | None = None,
) -> str:
    profile = load_project_profile(root)
    harness_config = profile.get(harness, {})
    aliases = harness_config.get("aliases", {})

    def resolve_alias(value: str | None) -> str | None:
        if value is None:
            return None
        return str(aliases.get(value, value))

    if explicit_model:
        return resolve_alias(explicit_model) or explicit_model

    phase_models = harness_config.get("phase_models", {})
    if phase:
        phase_model = resolve_alias(phase_models.get(phase))
        if phase_model:
            return phase_model

    packet_models = harness_config.get("packet_models", {})
    packet_type = packet_type_from_id(packet_id)
    if packet_type:
        packet_model = resolve_alias(packet_models.get(packet_type))
        if packet_model:
            return packet_model

    default_model = resolve_alias(harness_config.get("default_model"))
    if default_model:
        return default_model
    if harness == "pi":
        return "qwen/qwen3-coder-next-q6k"
    return "llama/qwen/qwen3-coder-next"


def resolve_opencode_model(
    root: Path,
    *,
    explicit_model: str | None = None,
    phase: str | None = None,
    packet_id: str | None = None,
) -> str:
    return resolve_harness_model(
        root,
        harness="opencode",
        explicit_model=explicit_model,
        phase=phase,
        packet_id=packet_id,
    )


def opencode_config_path() -> Path:
    return Path.home() / ".config" / "opencode" / "opencode.json"


def pi_models_config_path() -> Path:
    return Path.home() / ".pi" / "agent" / "models.json"


def load_opencode_config() -> dict:
    path = opencode_config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_pi_models_config() -> dict:
    path = pi_models_config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def split_provider_model(model: str) -> tuple[str | None, str]:
    if "/" not in model:
        return None, model
    provider, model_id = model.split("/", 1)
    return provider, model_id


def resolve_provider_model_aliases(model: str) -> dict:
    provider_name, model_id = split_provider_model(model)
    config = load_opencode_config()
    providers = config.get("provider", {})
    provider = providers.get(provider_name or "", {})
    models = provider.get("models", {})
    model_entry = models.get(model_id, {})
    aliases: set[str] = {model}
    if provider_name and model_id:
        aliases.add(model_id)
    for key in ("name", "model"):
        value = model_entry.get(key)
        if isinstance(value, str) and value:
            aliases.add(value)
    return {
        "provider": provider_name,
        "model_id": model_id,
        "provider_base_url": provider.get("options", {}).get("baseURL"),
        "aliases": sorted(aliases),
    }


def resolve_pi_model_aliases(model: str) -> dict:
    config = load_pi_models_config()
    providers = config.get("providers", {})
    aliases: set[str] = {model}
    matched_provider_name: str | None = None
    matched_provider: dict | None = None
    matched_model: dict | None = None

    for provider_name, provider in providers.items():
        for model_entry in provider.get("models", []):
            if not isinstance(model_entry, dict):
                continue
            candidates = {
                str(model_entry.get("id", "")),
                str(model_entry.get("name", "")),
                str(model_entry.get("model", "")),
            }
            candidates = {value for value in candidates if value and value != "None"}
            if model in candidates:
                matched_provider_name = str(provider_name)
                matched_provider = provider
                matched_model = model_entry
                aliases.update(candidates)
                break
        if matched_model is not None:
            break

    if matched_model is None:
        return {
            "provider": None,
            "model_id": model,
            "provider_base_url": None,
            "aliases": sorted(aliases),
        }

    return {
        "provider": matched_provider_name,
        "model_id": matched_model.get("id"),
        "provider_base_url": matched_provider.get("baseUrl") if isinstance(matched_provider, dict) else None,
        "aliases": sorted(aliases),
    }


def fetch_provider_active_models(base_url: str) -> list[str]:
    parsed = urlparse(base_url)
    models_url = parsed._replace(path="/v1/models", params="", query="", fragment="").geturl()
    with urlopen(models_url, timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
    candidates: set[str] = set()
    if isinstance(payload, dict):
        for item in payload.get("data", []):
            if isinstance(item, dict):
                for key in ("id", "name", "model"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        candidates.add(value)
                for alias in item.get("aliases", []):
                    if isinstance(alias, str) and alias:
                        candidates.add(alias)
        for item in payload.get("models", []):
            if isinstance(item, dict):
                for key in ("id", "name", "model"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        candidates.add(value)
    return sorted(candidates)


def check_active_opencode_model(model: str) -> dict:
    resolved = resolve_provider_model_aliases(model)
    provider_base_url = resolved.get("provider_base_url")
    aliases = resolved.get("aliases", [])
    payload = {
        "expected_model": model,
        "provider": resolved.get("provider"),
        "provider_base_url": provider_base_url,
        "expected_aliases": aliases,
        "active_models": [],
        "matches_active_model": None,
        "warning": None,
    }
    if not provider_base_url:
        payload["warning"] = "provider base URL unavailable for model sanity check"
        return payload
    try:
        active_models = fetch_provider_active_models(str(provider_base_url))
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        payload["warning"] = f"could not query active provider model: {exc}"
        return payload
    payload["active_models"] = active_models
    matches = bool(set(active_models) & set(aliases))
    payload["matches_active_model"] = matches
    if not matches:
        payload["warning"] = (
            "resolved OpenCode model does not match the currently served provider model"
        )
    return payload


def check_active_pi_model(model: str) -> dict:
    resolved = resolve_pi_model_aliases(model)
    provider_base_url = resolved.get("provider_base_url")
    aliases = resolved.get("aliases", [])
    payload = {
        "expected_model": model,
        "provider": resolved.get("provider"),
        "provider_base_url": provider_base_url,
        "expected_aliases": aliases,
        "active_models": [],
        "matches_active_model": None,
        "warning": None,
    }
    if not provider_base_url:
        payload["warning"] = "provider base URL unavailable for model sanity check"
        return payload
    try:
        active_models = fetch_provider_active_models(str(provider_base_url))
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        payload["warning"] = f"could not query active provider model: {exc}"
        return payload
    payload["active_models"] = active_models
    matches = bool(set(active_models) & set(aliases))
    payload["matches_active_model"] = matches
    if not matches:
        payload["warning"] = "resolved Pi Agent model does not match the currently served provider model"
    return payload


def check_active_harness_model(harness: str, model: str) -> dict:
    if harness == "pi":
        return check_active_pi_model(model)
    return check_active_opencode_model(model)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def validate_handoff(data: dict) -> None:
    missing = [field for field in REQUIRED_HANDOFF_FIELDS if field not in data]
    if missing:
        raise RuntimeError(f"handoff Markdown missing required fields: {', '.join(missing)}")


def parse_slice_markdown(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"slice Markdown not found: {path}")
    markdown = path.read_text(encoding="utf-8")
    _title, sections = parse_markdown_sections(markdown)
    inline_values: dict[str, str] = {}
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        for prefix in ("Group ID:", "Primary Jira Key:", "Secondary Jira Keys:"):
            if line.startswith(prefix):
                inline_values[prefix[:-1]] = line.split(":", 1)[1].strip()
    primary_issue = inline_values.get("Primary Jira Key", single_bullet(sections.get("Primary Jira Key", [])))
    secondary = inline_values.get("Secondary Jira Keys", single_bullet(sections.get("Secondary Jira Keys", []), "None"))
    secondary_issues = [] if secondary == "None" else [part.strip() for part in secondary.split(",") if part.strip()]
    pr_primary = primary_issue
    pr_additional = list(secondary_issues)
    for item in bullet_values(sections.get("PR Traceability", [])):
        if item.startswith("Primary:"):
            pr_primary = item.split(":", 1)[1].strip()
        elif item.startswith("Additional:"):
            extra = item.split(":", 1)[1].strip()
            pr_additional = [] if extra == "None" else [part.strip() for part in extra.split(",") if part.strip()]
    source_context = {
        "epic_review_date": "unknown-date",
        "implementation_group_reason": "",
    }
    for item in bullet_values(sections.get("Source Review Context", [])):
        if item.startswith("Derived from epic review of "):
            tail = item.split(" on ", 1)
            if len(tail) == 2:
                source_context["epic_review_date"] = tail[1].rstrip(".")
        else:
            source_context["implementation_group_reason"] = item
    return {
        "schema_version": "v1",
        "epic_key": path.parent.parent.name,
        "group_id": inline_values.get("Group ID", path.stem),
        "primary_issue": primary_issue,
        "secondary_issues": secondary_issues,
        "goal": single_bullet(sections.get("Goal", [])),
        "branch_name": single_bullet(sections.get("Branch Recommendation", [])),
        "pr_traceability": {
            "primary_issue": pr_primary or primary_issue,
            "additional_issues": pr_additional,
        },
        "entry_criteria": [] if bullet_values(sections.get("Entry Criteria", [])) == ["None"] else bullet_values(sections.get("Entry Criteria", [])),
        "exit_criteria": [] if bullet_values(sections.get("Exit Criteria", [])) == ["None"] else bullet_values(sections.get("Exit Criteria", [])),
        "repo_surfaces": [] if bullet_values(sections.get("Repo Surfaces", [])) == ["None"] else bullet_values(sections.get("Repo Surfaces", [])),
        "implementation_steps": [] if bullet_values(sections.get("Implementation Steps", [])) == ["None"] else bullet_values(sections.get("Implementation Steps", [])),
        "validation_steps": [] if bullet_values(sections.get("Validation Steps", [])) == ["None"] else bullet_values(sections.get("Validation Steps", [])),
        "risks": [] if bullet_values(sections.get("Risks and Constraints", [])) == ["None"] else bullet_values(sections.get("Risks and Constraints", [])),
        "open_questions": [] if bullet_values(sections.get("Open Questions", [])) == ["None"] else bullet_values(sections.get("Open Questions", [])),
        "source_context": source_context,
    }


def load_handoff(root: Path, epic_key: str, group_id: str) -> tuple[dict, Path]:
    path = slice_markdown_path(root, epic_key, group_id)
    data = parse_slice_markdown(path)
    validate_handoff(data)
    return data, path


def load_execution_input(root: Path, epic_key: str, group_id: str, packet_id: str | None = None) -> tuple[dict, Path]:
    if not packet_id:
        return load_handoff(root, epic_key, group_id)
    output_path = compiled_packet_json_path(root, epic_key, packet_id)
    compile_script = Path(__file__).resolve().parents[2] / "epic-slice-plan" / "scripts" / "compile_packet_markdown.py"
    cmd = [
        sys.executable,
        str(compile_script),
        epic_key,
        group_id,
        packet_id,
        "--repo-root",
        str(root),
        "--output",
        str(output_path),
    ]
    run_cmd(cmd)
    data = read_json(output_path)
    validate_handoff(data)
    return data, output_path


def resolve_approved_plan_path(
    root: Path,
    epic_key: str,
    packet_id: str | None,
    approved_plan_arg: str | None,
) -> Path | None:
    if approved_plan_arg:
        return Path(approved_plan_arg).resolve()
    if packet_id:
        candidate = implementation_plan_artifact_path(root, epic_key, packet_id)
        if candidate.exists():
            return candidate
        legacy = legacy_opencode_plan_artifact_path(root, epic_key, packet_id)
        if legacy.exists():
            return legacy
    return None


def sanitize_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-") or "session"


def slice_title(epic_key: str, group_id: str, phase: str | None = None, packet_id: str | None = None) -> str:
    base = f"slice:{epic_key}:{packet_id or group_id}"
    if phase == "planning":
        return f"{base}:plan-first"
    if phase == "implementing":
        return f"{base}:implement-from-plan"
    return base


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"command failed: {' '.join(cmd)}")
    return proc


def tmux_has_session(name: str) -> bool:
    proc = subprocess.run(["tmux", "has-session", "-t", name], check=False, capture_output=True, text=True)
    return proc.returncode == 0


def ensure_pm_dawn_ignored(root: Path) -> dict:
    entry = ".pm-dawn/"
    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8").splitlines()
        if entry in content:
            return {"status": "already_ignored", "path": str(gitignore)}
    exclude = root / ".git" / "info" / "exclude"
    if exclude.exists():
        content = exclude.read_text(encoding="utf-8").splitlines()
        if entry not in content:
            text = exclude.read_text(encoding="utf-8")
            suffix = "" if text.endswith("\n") or text == "" else "\n"
            exclude.write_text(text + suffix + entry + "\n", encoding="utf-8")
            return {"status": "added_to_git_info_exclude", "path": str(exclude)}
        return {"status": "already_ignored", "path": str(exclude)}
    return {"status": "unprotected", "path": None}


def opencode_server_session_name(root: Path) -> str:
    return f"opencode-server-{sanitize_name(root.name)}"


def pi_slice_tmux_session_name(epic_key: str, group_id: str, packet_id: str | None = None) -> str:
    return f"pi-{sanitize_name(epic_key)}-{sanitize_name(packet_id or group_id)}"


def opencode_slice_tmux_session_name(epic_key: str, group_id: str, packet_id: str | None = None) -> str:
    return f"opencode-{sanitize_name(epic_key)}-{sanitize_name(packet_id or group_id)}"


def pi_session_dir(root: Path, epic_key: str, group_id: str, packet_id: str | None = None, phase: str | None = None) -> Path:
    leaf = sanitize_name(packet_id or group_id)
    phase_leaf = sanitize_name(phase or "implementing")
    return root / ".pm-dawn" / "epics" / epic_key / "ops" / "runs" / "pi-sessions" / leaf / phase_leaf


def pi_console_log_path(session_dir: Path) -> Path:
    return session_dir / "console.log"


def _zsh_command(script: str) -> str:
    return f"/bin/zsh -lc {shlex.quote(script)}"


def launch_tmux_session_with_tail(
    *,
    session_name: str,
    cwd: Path,
    runner_script: str,
    tail_script: str,
) -> None:
    run_cmd(["tmux", "new-session", "-d", "-s", session_name, "-c", str(cwd), _zsh_command(runner_script)])
    run_cmd(["tmux", "split-window", "-v", "-t", f"{session_name}:0", "-c", str(cwd), _zsh_command(tail_script)])
    run_cmd(["tmux", "select-layout", "-t", f"{session_name}:0", "even-vertical"])


def pi_runner_script(*, root: Path, session_dir: Path, command: str) -> str:
    console_log = pi_console_log_path(session_dir)
    return (
        f"cd {shlex.quote(str(root))} && "
        f"mkdir -p {shlex.quote(str(session_dir))} && "
        "export PYTHONUNBUFFERED=1 && "
        f"{{ {command}; }} 2>&1 | tee -a {shlex.quote(str(console_log))}; "
        'runner_exit=${pipestatus[1]:-0}; '
        'printf "\\n[pm-dawn] runner exited with status %s\\n" "$runner_exit"; '
        "exec /bin/zsh -i"
    )


def pi_tail_script(*, session_dir: Path) -> str:
    session_dir_quoted = shlex.quote(str(session_dir))
    return (
        f"mkdir -p {session_dir_quoted} && "
        'echo "[pm-dawn] waiting for pi session log..." && '
        "while true; do "
        f"file=$(find {session_dir_quoted} -maxdepth 1 -type f -name '*.jsonl' | head -n 1); "
        'if [ -n "$file" ]; then '
        'echo "[pm-dawn] tailing $file"; '
        'tail -n +1 -F "$file"; '
        "break; "
        "fi; "
        "sleep 1; "
        "done"
    )


def list_sessions_json(max_count: int = 50) -> list[dict]:
    proc = run_cmd(["opencode", "session", "list", "--format", "json", "--max-count", str(max_count)])
    data = json.loads(proc.stdout or "[]")
    return data if isinstance(data, list) else []


def latest_session_by_title(title: str) -> dict | None:
    matches = [item for item in list_sessions_json() if item.get("title") == title]
    if not matches:
        return None
    matches.sort(key=lambda item: item.get("time", {}).get("updated", 0), reverse=True)
    return matches[0]


def build_launch_prompt(
    handoff: dict,
    handoff_path: Path,
    root: Path,
    *,
    phase: str = "implementing",
    approved_plan_path: Path | None = None,
) -> str:
    repo_name = root.name
    validation_command = full_suite_command(root)
    secondary = ", ".join(handoff.get("secondary_issues", [])) or "none"
    if phase == "planning":
        return f"""Read and follow AGENTS.md and CONTRIBUTING.md before making changes.

Then read the epic slice handoff at {handoff_path.relative_to(root)}.

This is a plan-first run. Do not edit files, create branches, or make any code changes yet.

Your task for this session is only to:
- inspect the handoff and relevant repo surfaces
- produce a concrete implementation plan for {handoff['primary_issue']} and {', '.join(handoff.get('secondary_issues', [])) or 'the scoped slice'}
- identify the exact files, interfaces, tests, and validation steps you expect to touch
- call out any ambiguity, boundary risk, or handoff weakness before implementation starts

Execution rules:
- Treat the handoff input as the source of truth for scope, branch naming, traceability, implementation steps, validation steps, risks, and exit criteria.
- Work only on the primary and secondary Jira issues listed in the handoff.
- Do not widen scope beyond the handoff.
- If the handoff is ambiguous or incomplete, stop and report the ambiguity instead of inventing requirements.
- Prefer the repo's documented full validation command where applicable ({validation_command}).
- Do not start implementation in this run.
- Do not edit any files in this run.
- Do not switch branches in this run.

At the end, provide only:
- implementation plan
- expected files/packages to change
- expected tests/validation
- open questions or blockers
"""

    plan_clause = ""
    plan_rules = ""
    if approved_plan_path:
        relative_plan = approved_plan_path.relative_to(root)
        plan_clause = f"\nThen read the approved plan at {relative_plan}.\n"
        if approved_plan_path.name.endswith(".implementation-plan.md") or approved_plan_path.name.endswith(".opencode-plan.md"):
            plan_rules = f"""
- You previously generated an initial draft plan for this packet.
- {relative_plan} is the reviewed and corrected implementation brief for this packet.
- Treat {relative_plan} as superseding your original draft plan.
- The handoff remains authoritative for scope, constraints, validation expectations, and Jira traceability.
- The reviewed implementation brief is authoritative for concrete implementation approach.
- Do not replace the reviewed implementation brief with a new plan unless you find a real conflict in the repo.
- If the reviewed implementation brief contains a seam assumption that the repo contradicts, stop and report the conflict instead of improvising.
- If the handoff and reviewed implementation brief conflict, stop and report the conflict instead of choosing one silently.
"""
        else:
            plan_rules = """
- Treat the approved plan markdown as the authoritative implementation plan when it is provided.
- If the handoff and approved plan conflict, stop and report the conflict instead of choosing one silently.
"""

    return f"""Read and follow AGENTS.md and CONTRIBUTING.md before making changes.

Then read the epic slice handoff at {handoff_path.relative_to(root)}.{plan_clause}
This is an implementation-only run starting from an already approved plan. Implement only that slice in this repository.

Repository:
- {repo_name}

Authoritative execution inputs:
- Primary Jira key: {handoff['primary_issue']}
- Secondary Jira keys: {secondary}
- Branch name: {handoff['branch_name']}
- Goal: {handoff['goal']}
{f"- Packet type: {handoff.get('packet_type')}" if handoff.get('packet_type') else ""}
{f"- Risk class: {handoff.get('risk_class')}" if handoff.get('risk_class') else ""}
{f"- Recommended executor: {handoff.get('recommended_executor')}" if handoff.get('recommended_executor') else ""}

Execution rules:
- Treat the handoff input as the source of truth for scope, branch naming, traceability, implementation steps, validation steps, risks, and exit criteria.
- Work only on the primary and secondary Jira issues listed in the handoff.
- Work on the current branch only.
- Do not create a new branch in this run.
- Do not switch branches in this run.
- Follow the repository guidance in AGENTS.md and CONTRIBUTING.md, including commit message format and PR traceability expectations.
- Do not widen scope beyond the handoff.
- If the handoff is ambiguous or incomplete, stop and report the ambiguity instead of inventing behavior.
- Prefer the repo's documented full validation command where applicable ({validation_command}).
{chr(10).join(f"- Routing note: {item}" for item in handoff.get("routing_notes", []))}
{plan_rules.rstrip()}

Before editing:
- Read the handoff.
- Read the reviewed plan when one is provided.
- Create a short todo list limited to tasks that are inside the packet scope and reviewed plan.
- If you believe you need a todo item outside the packet scope, stop and report instead of expanding the task.
- Start with the listed implementation files and only search beyond them if you hit a concrete repo question.

Implementation steps:
{chr(10).join(f"- {step}" for step in handoff.get("implementation_steps", []))}

Validation steps:
{chr(10).join(f"- {step}" for step in handoff.get("validation_steps", []))}

At the end, summarize:
- files changed
- key implementation decisions
- validation run
- any remaining risks or blockers

If you believe the implementation pass is complete and ready for human review, as your final step run:
- python "/Users/evo/.codex/skills/epic-slice-implement/scripts/mark_slice_pending_review.py" {handoff['epic_key']} {handoff['group_id']} --repo-root {root}

Use that only to mark worker state as pending review.
Do not mark the packet completed in metadata; reviewer acceptance is separate.
"""


def build_steer_prompt(handoff: dict, handoff_path: Path, root: Path, steering_message: str) -> str:
    return f"""Continue the existing implementation session for {handoff['group_id']} using the same handoff at {handoff_path.relative_to(root)}.

Before proceeding:
- Re-read AGENTS.md and CONTRIBUTING.md if needed for branch, commit, validation, or PR traceability rules.
- Stay strictly within the handoff scope.

Steering update:
{steering_message}

If this steering conflicts with the handoff, stop and report the conflict instead of guessing.
"""


def attach_instructions(server_url: str | None, session_id: str | None, tmux_session: str | None, root: Path) -> list[str]:
    instructions: list[str] = []
    if tmux_session:
        instructions.append(f"tmux attach -t {tmux_session}")
    if server_url:
        cmd = f"opencode attach {server_url} --dir {root}"
        if session_id:
            cmd += f" --session {session_id}"
        instructions.append(cmd)
    return instructions


def pi_attach_instructions(tmux_session: str | None) -> list[str]:
    instructions: list[str] = []
    if tmux_session:
        instructions.append(f"tmux attach -t {tmux_session}")
        instructions.append(f"tmux list-panes -t {tmux_session} -F '#{{pane_index}} #{{pane_current_command}}'")
        instructions.append(f"tmux select-pane -t {tmux_session}:0.1")
    return instructions


def poll_for_session(title: str, timeout_seconds: int = 30) -> dict | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        found = latest_session_by_title(title)
        if found:
            return found
        time.sleep(1)
    return None


def export_session_json(session_id: str) -> dict:
    proc = run_cmd(["opencode", "export", session_id])
    stdout = proc.stdout.strip()
    start = stdout.find("{")
    if start == -1:
        raise RuntimeError(f"could not parse opencode export output for session {session_id}")
    try:
        return json.loads(stdout[start:])
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"could not decode opencode export output for session {session_id}: {exc}"
        ) from exc


def infer_phase(run_meta: dict, session_export: dict | None = None) -> str:
    explicit = run_meta.get("phase")
    if explicit:
        return explicit
    title = ""
    if session_export:
        title = session_export.get("info", {}).get("title", "")
    if "plan-first" in title:
        return "planning"
    if run_meta.get("last_action") == "prepare":
        return "planning"
    return "implementing"


def latest_completed_assistant_message(session_export: dict, *, require_text: bool = False) -> dict | None:
    assistants = [msg for msg in session_export.get("messages", []) if msg.get("info", {}).get("role") == "assistant"]
    completed = [msg for msg in assistants if msg.get("info", {}).get("time", {}).get("completed")]
    if require_text:
        completed = [msg for msg in completed if message_text(msg)]
    if not completed:
        return None
    completed.sort(key=lambda msg: msg.get("info", {}).get("time", {}).get("completed", 0))
    return completed[-1]


def latest_assistant_message(session_export: dict) -> dict | None:
    assistants = [msg for msg in session_export.get("messages", []) if msg.get("info", {}).get("role") == "assistant"]
    if not assistants:
        return None
    return assistants[-1]


def session_completion_state(session_export: dict) -> str:
    latest = latest_assistant_message(session_export)
    if not latest:
        return "in_progress"
    if not latest.get("info", {}).get("time", {}).get("completed"):
        return "in_progress"
    error = latest.get("info", {}).get("error", {})
    message = str(error.get("data", {}).get("message", "")).lower()
    if "timed out" in message:
        return "timed_out"
    finish = latest.get("info", {}).get("finish")
    if finish == "stop":
        return "completed"
    if finish == "tool-calls":
        return "failed"
    return "failed"


def session_runtime_status(run_meta: dict, completion_state: str) -> str:
    if completion_state == "completed":
        return "completed"
    if completion_state in {"failed", "timed_out"}:
        return completion_state
    runtime = run_meta.get("runtime", {})
    tmux_session = runtime.get("tmux_session") or run_meta.get("opencode", {}).get("tmux_session")
    server_tmux_session = runtime.get("server_tmux_session") or run_meta.get("opencode", {}).get("server_tmux_session")
    if tmux_session and tmux_has_session(tmux_session):
        return "running"
    if server_tmux_session and tmux_has_session(server_tmux_session):
        return "running"
    return "stopped"


def message_text(message: dict) -> str:
    texts: list[str] = []
    for part in message.get("parts", []):
        if part.get("type") == "text":
            text = part.get("text", "")
            if text:
                texts.append(text)
    return "\n".join(texts).strip()


def render_phase_artifact(
    *,
    epic_key: str,
    group_id: str,
    phase: str,
    session_export: dict,
    source_message: dict,
) -> str:
    session_info = session_export.get("info", {})
    completed_at = source_message.get("info", {}).get("time", {}).get("completed")
    body = message_text(source_message) or "(No assistant text captured.)"
    title = "Approved Plan" if phase == "planning" else "Implementation Result"
    lines = [
        f"# {epic_key} / {group_id} / {title}",
        "",
        f"- Phase: {phase}",
        f"- Session ID: {session_info.get('id')}",
        f"- Session Title: {session_info.get('title')}",
    ]
    if completed_at:
        lines.append(f"- Completed: {completed_at}")
    lines += [
        "",
        "## Captured Output",
        "",
        body,
        "",
    ]
    return "\n".join(lines)
