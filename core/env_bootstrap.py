"""Load API keys with explicit precedence layering."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

from core.user_paths import USER_ENV_FILE, ensure_user_dirs

# Explicit env file path (highest file layer). Example:
#   AI_SYNAPSE_ENV=~/work.env python -m ai_engine tui
ENV_FILE_OVERRIDE_VAR = "AI_SYNAPSE_ENV"

_bootstrapped = False


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return {
        key: value
        for key, value in dotenv_values(path).items()
        if key and value is not None
    }


def _merge_layers(*layers: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for layer in layers:
        merged.update(layer)
    return merged


def bootstrap_user_environment(*, force: bool = False) -> None:
    """
    Merge env files into ``os.environ`` with predictable precedence.

    Priority (highest wins on same variable name):

    1. **Process environment** — already exported in the shell / container
    2. **``AI_SYNAPSE_ENV``** — path to an explicit env file
    3. **``./.env``** — in the current working directory (venv / git clone)
    4. **``~/.ai-engine/.env``** — global config for pip installs

    Different variable names from each layer are merged together.
    """
    global _bootstrapped
    if _bootstrapped and not force:
        return

    ensure_user_dirs()

    # Snapshot before applying file layers — these keys are never overwritten.
    process_keys = frozenset(os.environ)

    global_layer = _read_env_file(USER_ENV_FILE)
    cwd_layer = _read_env_file(Path.cwd() / ".env")

    explicit_path = os.environ.get(ENV_FILE_OVERRIDE_VAR, "").strip()
    explicit_layer = (
        _read_env_file(Path(explicit_path).expanduser())
        if explicit_path
        else {}
    )

    merged = _merge_layers(global_layer, cwd_layer, explicit_layer)

    for key, value in merged.items():
        if key not in process_keys:
            os.environ[key] = value

    _bootstrapped = True


def user_env_status() -> dict[str, str | bool | None]:
    """Summary for diagnostics — which env files exist and apply."""
    explicit = os.environ.get(ENV_FILE_OVERRIDE_VAR, "").strip()
    cwd_env = Path.cwd() / ".env"
    explicit_path = Path(explicit).expanduser() if explicit else None
    return {
        "home": str(USER_ENV_FILE.parent),
        "global_env": str(USER_ENV_FILE),
        "global_exists": USER_ENV_FILE.is_file(),
        "cwd": os.getcwd(),
        "cwd_env": str(cwd_env),
        "cwd_exists": cwd_env.is_file(),
        "explicit_env": str(explicit_path) if explicit_path else None,
        "explicit_exists": bool(explicit_path and explicit_path.is_file()),
    }
