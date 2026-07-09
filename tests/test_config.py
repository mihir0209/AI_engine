"""Tests for config.py module"""

import pytest
from pydantic import ValidationError


def test_import_config():
    from config import AI_CONFIGS, ENGINE_SETTINGS, AUTODECIDE_CONFIG, verbose_print
    assert isinstance(AI_CONFIGS, dict)
    assert isinstance(ENGINE_SETTINGS, dict)
    assert isinstance(AUTODECIDE_CONFIG, dict)
    assert callable(verbose_print)


def test_providers_have_required_fields():
    from config import AI_CONFIGS
    required_fields = ["id", "priority", "endpoint", "model", "method", "format", "enabled"]
    for name, config in AI_CONFIGS.items():
        for field in required_fields:
            assert field in config, f"Provider '{name}' missing field '{field}'"


def test_providers_have_valid_ids():
    from config import AI_CONFIGS
    ids = [c["id"] for c in AI_CONFIGS.values()]
    assert len(ids) == len(set(ids)), "Duplicate provider IDs found"


def test_providers_have_api_keys_or_no_auth():
    from config import AI_CONFIGS
    for name, config in AI_CONFIGS.items():
        if config.get("auth_type"):
            assert "api_keys" in config, f"Provider '{name}' needs auth but has no api_keys"
            assert isinstance(config["api_keys"], list), f"Provider '{name}' api_keys must be list"


def test_valid_formats():
    from config import AI_CONFIGS
    valid_formats = {"openai", "gemini", "cohere", "a3z_get", "cloudflare", "ollama", "flowith", "minimax"}
    for name, config in AI_CONFIGS.items():
        assert config["format"] in valid_formats, f"Provider '{name}' has invalid format '{config['format']}'"


def test_engine_settings_keys():
    from config import ENGINE_SETTINGS
    assert "default_timeout" in ENGINE_SETTINGS
    assert "consecutive_failure_limit" in ENGINE_SETTINGS
    assert "key_rotation_enabled" in ENGINE_SETTINGS
    assert "provider_rotation_enabled" in ENGINE_SETTINGS


def test_verbose_print(capsys):
    from config import verbose_print, ENGINE_SETTINGS
    original = ENGINE_SETTINGS.get("verbose_mode", False)

    ENGINE_SETTINGS["verbose_mode"] = True
    verbose_print("test message")
    captured = capsys.readouterr()
    assert "test message" in captured.out

    ENGINE_SETTINGS["verbose_mode"] = False
    verbose_print("should not print")
    captured = capsys.readouterr()
    assert "should not print" not in captured.out

    ENGINE_SETTINGS["verbose_mode"] = original


def test_verbose_print_override(capsys):
    from config import verbose_print, ENGINE_SETTINGS
    original = ENGINE_SETTINGS.get("verbose_mode", False)

    ENGINE_SETTINGS["verbose_mode"] = False
    verbose_print("override message", verbose_override=True)
    captured = capsys.readouterr()
    assert "override message" in captured.out

    ENGINE_SETTINGS["verbose_mode"] = original


def test_autodecide_config():
    from config import AUTODECIDE_CONFIG
    assert "enabled" in AUTODECIDE_CONFIG
    assert "cache_duration" in AUTODECIDE_CONFIG
    assert isinstance(AUTODECIDE_CONFIG["cache_duration"], int)
    assert AUTODECIDE_CONFIG["cache_duration"] > 0


def test_provider_config_modes_default():
    from core.config import ProviderConfig
    cfg = ProviderConfig(id=1, priority=1, endpoint="http://x", model="m")
    assert cfg.modes == ["live"]


def test_provider_config_modes_accepts_both():
    from core.config import ProviderConfig
    cfg = ProviderConfig(id=1, priority=1, endpoint="http://x", model="m", modes=["live", "testing"])
    assert "testing" in cfg.modes


def test_provider_config_modes_rejects_empty_list():
    from core.config import ProviderConfig

    with pytest.raises(ValidationError, match="modes must be non-empty"):
        ProviderConfig(id=1, priority=1, endpoint="http://x", model="m", modes=[])


def test_provider_config_modes_rejects_invalid_value():
    from core.config import ProviderConfig

    with pytest.raises(ValidationError, match="modes must be non-empty"):
        ProviderConfig(id=1, priority=1, endpoint="http://x", model="m", modes=["production"])


def test_provider_config_modes_dedupes_preserving_order():
    from core.config import ProviderConfig

    cfg = ProviderConfig(
        id=1,
        priority=1,
        endpoint="http://x",
        model="m",
        modes=["live", "testing", "live", "testing"],
    )
    assert cfg.modes == ["live", "testing"]


def test_test_harness_provider_exists():
    from core.config import AI_CONFIGS

    assert "test_harness" in AI_CONFIGS
    harness = AI_CONFIGS["test_harness"]
    assert harness["id"] == 99
    assert harness["modes"] == ["testing"]
    assert harness["api_keys"] == ["test-key-alpha", "test-key-beta", "test-key-gamma"]
    assert "127.0.0.1:18765" in harness["endpoint"]
    assert "127.0.0.1:18765" in harness["model_endpoint"]
