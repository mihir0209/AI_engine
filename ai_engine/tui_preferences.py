"""User preferences for the AI Synapse TUI (~/.ai-engine/preferences.json)."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

PREFERENCES_FILE = Path.home() / ".ai-engine" / "preferences.json"
_lock = threading.Lock()


def _default_preferences() -> dict[str, Any]:
    return {
        "favorite_models": [],
        "default_model": "default",
        "default_provider": None,
    }


class PreferencesStore:
    """Read/write TUI user preferences."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PREFERENCES_FILE

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return _default_preferences()
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return _default_preferences()
        if not isinstance(data, dict):
            return _default_preferences()
        prefs = _default_preferences()
        prefs["favorite_models"] = list(data.get("favorite_models", []))
        prefs["default_model"] = str(data.get("default_model", "default") or "default")
        provider = data.get("default_provider")
        if provider in (None, "", "auto"):
            prefs["default_provider"] = None
        else:
            prefs["default_provider"] = str(provider)
        return prefs

    def save(self, prefs: dict[str, Any]) -> None:
        with _lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            provider = prefs.get("default_provider")
            if provider in (None, "", "auto"):
                provider = None
            payload = {
                "favorite_models": list(prefs.get("favorite_models", [])),
                "default_model": str(prefs.get("default_model", "default") or "default"),
                "default_provider": provider,
            }
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            tmp.replace(self.path)

    def migrate_favorite_models_from_meta(self, models: list[str]) -> list[str]:
        """One-time merge of legacy meta.json favorite_models into preferences."""
        if not models:
            return self.load().get("favorite_models", [])
        prefs = self.load()
        merged: list[str] = list(prefs.get("favorite_models", []))
        for key in models:
            if key not in merged:
                merged.append(key)
        prefs["favorite_models"] = merged
        self.save(prefs)
        return merged

    def save_defaults(self, *, model: str, provider: str | None) -> None:
        """Persist default model and provider for new sessions."""
        prefs = self.load()
        prefs["default_model"] = model or "default"
        if provider in (None, "", "auto"):
            prefs["default_provider"] = None
        else:
            prefs["default_provider"] = provider
        self.save(prefs)