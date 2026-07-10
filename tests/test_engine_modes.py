"""Tests for AI_ENGINE_MODE provider filtering."""

import importlib
import os

import pytest

import core.ai_engine as ai_engine_module


@pytest.fixture(autouse=True)
def reset_engine_mode():
    """Restore AI_ENGINE_MODE and reload ai_engine after each test."""
    original_mode = os.environ.get("AI_ENGINE_MODE")
    yield
    if original_mode is None:
        os.environ.pop("AI_ENGINE_MODE", None)
    else:
        os.environ["AI_ENGINE_MODE"] = original_mode
    importlib.reload(ai_engine_module)


def _reload_engine_with_mode(monkeypatch, mode: str):
    monkeypatch.setenv("AI_ENGINE_MODE", mode)
    importlib.reload(ai_engine_module)
    return ai_engine_module.AI_engine(verbose=False)


@pytest.mark.parametrize(
    "mode,should_include",
    [
        ("live", False),
        ("testing", True),
        ("all", False),
    ],
)
def test_load_enabled_providers_filters_test_harness_by_engine_mode(
    monkeypatch, mode, should_include
):
    engine = _reload_engine_with_mode(monkeypatch, mode)
    if should_include:
        assert "test_harness" in engine.providers
    else:
        assert "test_harness" not in engine.providers


@pytest.mark.parametrize(
    "engine_mode,provider_modes,expected",
    [
        ("all", ["testing"], False),
        ("all", ["live"], True),
        ("live", ["live"], True),
        ("live", ["testing"], False),
        ("live", ["live", "testing"], True),
        ("testing", ["testing"], True),
        ("testing", ["live"], False),
        ("testing", ["live", "testing"], True),
    ],
)
def test_provider_matches_mode(monkeypatch, engine_mode, provider_modes, expected):
    engine = _reload_engine_with_mode(monkeypatch, engine_mode)
    config = {"modes": provider_modes}
    assert engine._provider_matches_mode(config) is expected


def test_provider_matches_mode_defaults_to_live(monkeypatch):
    engine = _reload_engine_with_mode(monkeypatch, "live")
    assert engine._provider_matches_mode({}) is True
    assert engine._provider_matches_mode({"modes": ["testing"]}) is False
