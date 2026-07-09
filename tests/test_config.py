"""Tests for config.py module"""


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


def test_test_harness_provider_exists():
    from core.config import AI_CONFIGS
    assert "test_harness" in AI_CONFIGS
    assert AI_CONFIGS["test_harness"]["modes"] == ["testing"]
    assert len(AI_CONFIGS["test_harness"]["api_keys"]) == 3
