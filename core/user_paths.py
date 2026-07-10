"""Canonical per-user paths for AI Synapse (pip install, TUI, server)."""
from __future__ import annotations

from pathlib import Path

AI_ENGINE_HOME = Path.home() / ".ai-engine"
USER_ENV_FILE = AI_ENGINE_HOME / ".env"
USER_CONFIG_FILE = AI_ENGINE_HOME / "config.json"
USER_DATA_DIR = AI_ENGINE_HOME / "data"
MODEL_CACHE_FILE = USER_DATA_DIR / "model_cache.json"


def ensure_user_dirs() -> None:
    AI_ENGINE_HOME.mkdir(parents=True, exist_ok=True)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
