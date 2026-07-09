"""Tests for TUI user preferences."""
import json

from ai_engine.tui.preferences import PreferencesStore


def test_preferences_roundtrip(tmp_path):
    path = tmp_path / "preferences.json"
    store = PreferencesStore(path=path)
    store.save({"favorite_models": ["gpt-4o|groq"]})
    loaded = store.load()
    assert loaded["favorite_models"] == ["gpt-4o|groq"]
    assert json.loads(path.read_text(encoding="utf-8"))["favorite_models"] == [
        "gpt-4o|groq"
    ]


def test_defaults_roundtrip(tmp_path):
    path = tmp_path / "preferences.json"
    store = PreferencesStore(path=path)
    store.save_defaults(model="gpt-4o", provider="groq")
    loaded = store.load()
    assert loaded["default_model"] == "gpt-4o"
    assert loaded["default_provider"] == "groq"
    store.save_defaults(model="default", provider=None)
    loaded = store.load()
    assert loaded["default_provider"] is None


def test_migrate_favorite_models_from_meta(tmp_path):
    path = tmp_path / "preferences.json"
    store = PreferencesStore(path=path)
    merged = store.migrate_favorite_models_from_meta(
        ["claude-3|openrouter", "gpt-4o|groq"]
    )
    assert merged == ["claude-3|openrouter", "gpt-4o|groq"]
    again = store.migrate_favorite_models_from_meta(["gpt-4o|groq"])
    assert again == ["claude-3|openrouter", "gpt-4o|groq"]