from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen


def runtime_home() -> Path | None:
    override = os.environ.get("PM_DAWN_HOME") or os.environ.get("HOME")
    if override:
        return Path(override).expanduser()
    try:
        return Path.home()
    except RuntimeError:
        return None


def provider_timeout_seconds() -> float:
    raw = os.environ.get("PM_DAWN_PROVIDER_TIMEOUT_SECONDS", "2")
    try:
        return float(raw)
    except ValueError:
        return 2.0


def opencode_config_path() -> Path:
    override = os.environ.get("PM_DAWN_OPENCODE_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config).expanduser() / "opencode" / "opencode.json"
    home = runtime_home()
    if home is not None:
        return home / ".config" / "opencode" / "opencode.json"
    return Path(".config") / "opencode" / "opencode.json"


def pi_models_config_path() -> Path:
    override = os.environ.get("PM_DAWN_PI_MODELS_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    home = runtime_home()
    if home is not None:
        return home / ".pi" / "agent" / "models.json"
    return Path(".pi") / "agent" / "models.json"


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
    with urlopen(models_url, timeout=provider_timeout_seconds()) as response:
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
        payload["warning"] = "resolved OpenCode model does not match the currently served provider model"
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


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"required CLI '{cmd[0]}' not found in PATH") from exc
    if check and proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.strip()
            or proc.stdout.strip()
            or f"command failed: {shlex.join(cmd)}"
        )
    return proc


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


def require_cli(command: str) -> None:
    if not command_available(command):
        raise RuntimeError(f"required CLI '{command}' not found in PATH")


def tmux_has_session(name: str) -> bool:
    if not command_available("tmux"):
        return False
    proc = subprocess.run(["tmux", "has-session", "-t", name], check=False, capture_output=True, text=True)
    return proc.returncode == 0


def resolved_shell_executable() -> str:
    candidates = [
        os.environ.get("PM_DAWN_SHELL"),
        os.environ.get("SHELL"),
        "zsh",
        "bash",
        "sh",
    ]
    for candidate in candidates:
        if candidate:
            resolved = shutil.which(str(Path(candidate).expanduser()))
            if resolved:
                return resolved
    raise RuntimeError("no usable shell found; set PM_DAWN_SHELL to an available shell executable")
