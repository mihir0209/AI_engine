"""Unit tests for key-rotation internals (_request_with_key_rotation, edge cases)."""
from datetime import datetime, timedelta
from unittest.mock import patch

from core.provider_requests import RequestResult

pytest_plugins = ["tests.test_ai_engine"]

from tests.test_ai_engine import _setup_rotation_provider  # noqa: E402


def test_rotate_api_key_defaults_enabled_when_setting_absent(engine):
    """Kill mutants that change get('key_rotation_enabled', True) default to None."""
    provider = _setup_rotation_provider(engine)
    engine.engine_settings.pop("key_rotation_enabled", None)
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    rotated = engine._rotate_api_key(provider)
    assert rotated in ("key-beta", "key-gamma")
    assert engine.provider_key_rotation[provider] != 0


def test_rotate_api_key_returns_none_for_missing_provider(engine):
    assert engine._rotate_api_key("missing_provider_xyz") is None


def test_rotate_api_key_returns_none_when_all_keys_null(engine):
    provider = _setup_rotation_provider(engine, keys=[None, None])
    assert engine._rotate_api_key(provider) is None


def test_rotate_api_key_returns_none_when_select_optimal_key_returns_none(engine):
    provider = _setup_rotation_provider(engine)
    with patch.object(engine, "_select_optimal_key", return_value=None):
        assert engine._rotate_api_key(provider) is None


def test_select_optimal_key_resets_expired_rate_limit_flag(engine):
    provider = _setup_rotation_provider(engine)
    engine.key_usage_stats[provider]["key_0"]["rate_limited"] = True
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now() - timedelta(seconds=120)
    selected = engine._select_optimal_key(provider)
    assert engine.key_usage_stats[provider]["key_0"]["rate_limited"] is False
    assert selected == 0


def test_select_optimal_key_verbose_logs_selection(engine_verbose):
    provider = _setup_rotation_provider(engine_verbose)
    selected = engine_verbose._select_optimal_key(provider)
    assert selected == 0


def test_roll_api_key_empty_api_keys_reports_zero_keys(engine):
    engine.providers["empty_keys_provider"] = {"enabled": True, "api_keys": []}
    result = engine.roll_api_key("empty_keys_provider")
    assert "0 key" in result.lower()


def test_roll_api_key_staying_message_when_rotation_picks_same_key(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    with patch.object(engine, "_rotate_api_key", return_value="key-alpha"):
        result = engine.roll_api_key(provider)
    assert "staying at key #0" in result.lower()


def test_roll_api_key_disabled_when_rotate_returns_none(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["key_rotation_enabled"] = False
    with patch.object(engine, "_rotate_api_key", return_value=None):
        result = engine.roll_api_key(provider)
    assert "disabled in engine settings" in result.lower()


def test_roll_api_key_handles_out_of_range_current_index(engine):
    provider = _setup_rotation_provider(engine, keys=["a", "b", "c"])
    engine.provider_key_rotation[provider] = 99
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    result = engine.roll_api_key(provider)
    assert "Rolled" in result or "rolled" in result.lower()


def test_handle_provider_failure_increments_usage_stats_failures(engine):
    provider = _setup_rotation_provider(engine)
    before = engine.usage_stats[provider]["failures"]
    engine._handle_provider_failure(provider, "internal server error", 500)
    assert engine.usage_stats[provider]["failures"] == before + 1
    assert engine.usage_stats[provider]["last_failure"] is not None


def test_handle_provider_failure_network_error_flags_provider(engine):
    provider = _setup_rotation_provider(engine)
    engine._handle_provider_failure(provider, "connection timeout", 0)
    assert provider in engine.flagged_keys
    assert engine.provider_key_rotation[provider] == 0


def test_handle_provider_failure_uses_response_json_for_classification(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    engine._handle_provider_failure(
        provider,
        "error",
        400,
        {"error": {"type": "rate_limit_exceeded"}},
    )
    assert engine.provider_key_rotation[provider] != 0


def test_request_with_key_rotation_success_first_attempt(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]
    with patch.object(engine, "_make_request", return_value=RequestResult(success=True, content="ok")):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])
    assert result.success is True
    assert result.content == "ok"


def test_request_with_key_rotation_retries_rate_limit_then_succeeds(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]
    calls = {"n": 0}

    def side_effect(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return RequestResult(success=False, error_message="rate limit", status_code=429)
        return RequestResult(success=True, content="recovered")

    with patch.object(engine, "_make_request", side_effect=side_effect):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])
    assert result.success is True
    assert calls["n"] == 2


def test_request_with_key_rotation_retries_auth_error_then_succeeds(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]
    calls = {"n": 0}

    def side_effect(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return RequestResult(success=False, error_message="invalid api key", status_code=401)
        return RequestResult(success=True, content="recovered")

    with patch.object(engine, "_make_request", side_effect=side_effect):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])
    assert result.success is True
    assert calls["n"] == 2


def test_request_with_key_rotation_stops_on_server_error(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]
    calls = {"n": 0}

    def side_effect(*_args, **_kwargs):
        calls["n"] += 1
        return RequestResult(success=False, error_message="internal server error", status_code=500)

    with patch.object(engine, "_make_request", side_effect=side_effect):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])
    assert result.success is False
    assert calls["n"] == 1


def test_request_with_key_rotation_respects_max_attempts(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]
    calls = {"n": 0}

    def side_effect(*_args, **_kwargs):
        calls["n"] += 1
        return RequestResult(success=False, error_message="rate limit", status_code=429)

    with patch.object(engine, "_make_request", side_effect=side_effect):
        result = engine._request_with_key_rotation(
            provider, config, [{"role": "user", "content": "hi"}], max_attempts=2
        )
    assert result.success is False
    assert calls["n"] == 2


def test_request_with_key_rotation_handles_exception(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]

    with patch.object(engine, "_make_request", side_effect=RuntimeError("boom")):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])
    assert result.success is False
    assert result.error_type == "provider_exception"
    assert "boom" in result.error_message


def test_request_with_key_rotation_empty_keys_single_attempt(engine):
    provider = _setup_rotation_provider(engine)
    engine.providers[provider]["api_keys"] = []
    config = engine.providers[provider]
    calls = {"n": 0}

    def side_effect(*_args, **_kwargs):
        calls["n"] += 1
        return RequestResult(success=False, error_message="rate limit", status_code=429)

    with patch.object(engine, "_make_request", side_effect=side_effect):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])
    assert result.success is False
    assert calls["n"] == 1
