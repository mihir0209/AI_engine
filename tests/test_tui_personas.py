"""Tests for TUI persona loading."""
import json

from ai_engine.tui.personas import find_persona, load_personas


def test_load_builtin_personas():
    personas = load_personas(personas_dir=__import__("pathlib").Path("/nonexistent"))
    assert len(personas) >= 4
    ids = {p.id for p in personas}
    assert "coder" in ids
    assert "reviewer" in ids


def test_user_persona_overrides_builtin(tmp_path):
    user_dir = tmp_path / "personas"
    user_dir.mkdir()
    (user_dir / "coder.json").write_text(
        json.dumps(
            {
                "id": "coder",
                "label": "My Coder",
                "emoji": "🛠",
                "system_prompt": "Custom coder prompt.",
            }
        ),
        encoding="utf-8",
    )
    personas = load_personas(personas_dir=user_dir)
    coder = find_persona(personas, "coder")
    assert coder is not None
    assert coder.label == "My Coder"
    assert coder.system_prompt == "Custom coder prompt."


def test_find_persona_by_label(tmp_path):
    personas = load_personas(personas_dir=tmp_path / "missing")
    arch = find_persona(personas, "Architect")
    assert arch is not None
    assert arch.id == "architect"
