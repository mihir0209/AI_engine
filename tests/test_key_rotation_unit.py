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


def test_request_with_key_rotation_missing_api_keys_config_does_not_crash(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider].copy()
    config.pop("api_keys", None)

    with patch.object(engine, "_make_request", return_value=RequestResult(success=False, error_message="rate limit", status_code=429)):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])

    assert result.success is False
    assert result.error_message == "rate limit"
    assert result.provider_used == provider


def test_request_with_key_rotation_passes_original_messages_to_make_request(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]
    messages = [{"role": "user", "content": "keep me"}]

    with patch.object(engine, "_make_request", return_value=RequestResult(success=True, content="ok")) as make_request:
        result = engine._request_with_key_rotation(provider, config, messages)

    assert result.success is True
    assert make_request.call_args.args[2] is messages


def test_handle_provider_failure_records_health_and_latency_with_provider(engine):
    provider = _setup_rotation_provider(engine)
    with (
        patch("core.ai_engine.health_monitor.record_check") as record_check,
        patch("core.ai_engine.latency_tracker.record") as record_latency,
    ):
        engine._handle_provider_failure(provider, "internal server error", 500)

    record_check.assert_called_once_with(provider, success=False, error="internal server error", status_code=500)
    record_latency.assert_called_once_with(provider, 10000, success=False)


def test_handle_provider_failure_marks_rate_limit_with_retry_after(engine):
    provider = _setup_rotation_provider(engine)
    with patch("core.ai_engine.rate_limit_manager.mark_rate_limited") as mark_rate_limited:
        engine._handle_provider_failure(provider, "rate limit", 429)

    mark_rate_limited.assert_called_once_with(provider, retry_after=60)


def test_select_optimal_key_returns_none_when_all_keys_in_cooldown(engine):
    provider = _setup_rotation_provider(engine)
    now = datetime.now()
    for key_id in engine.key_usage_stats[provider]:
        engine.key_usage_stats[provider][key_id]["rate_limited"] = True
        engine.key_usage_stats[provider][key_id]["last_used"] = now

    assert engine._select_optimal_key(provider) is None
    assert all(stats["rate_limited"] for stats in engine.key_usage_stats[provider].values())


def test_request_with_key_rotation_passes_model_and_records_success_stats(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]
    messages = [{"role": "user", "content": "hi"}]

    with (
        patch.object(engine, "_make_request", return_value=RequestResult(success=True, content="ok")) as make_request,
        patch.object(engine, "_update_stats") as update_stats,
    ):
        result = engine._request_with_key_rotation(provider, config, messages, model="custom-model")

    assert result.provider_used == provider
    assert result.response_time is not None
    assert 0 <= result.response_time < 5
    assert make_request.call_args.args[3] == "custom-model"
    update_stats.assert_called_once()
    assert update_stats.call_args.args[0] == provider
    assert update_stats.call_args.args[1] is True
    assert 0 <= update_stats.call_args.args[2] < 5


def test_handle_provider_failure_increments_existing_failure_count(engine):
    provider = _setup_rotation_provider(engine)
    engine.usage_stats[provider]["failures"] = 4

    engine._handle_provider_failure(provider, "internal server error", 500)

    assert engine.usage_stats[provider]["failures"] == 5
    assert engine.usage_stats[provider]["consecutive_failures"] == 1


def test_handle_provider_failure_flags_service_errors_for_ten_minutes(engine):
    provider = _setup_rotation_provider(engine)
    with patch.object(engine, "_flag_provider") as flag_provider:
        engine._handle_provider_failure(provider, "service unavailable", 503)

    flag_provider.assert_called_once_with(provider, duration_minutes=10)


def test_handle_provider_failure_verbose_logs_error_classification(engine_verbose):
    provider = _setup_rotation_provider(engine_verbose)
    with patch("core.ai_engine.verbose_print") as verbose_print_mock:
        engine_verbose._handle_provider_failure(provider, "internal server error", 500)

    assert any(
        args[0] == f"🔍 {provider} error classified as: server_error" and args[1] is True
        for args, _kwargs in verbose_print_mock.call_args_list
    )


def test_rotate_api_key_single_valid_key_does_not_mark_rate_limited(engine):
    provider = _setup_rotation_provider(engine, keys=[None, "only-key"])
    engine.provider_key_rotation[provider] = 1

    with patch.object(engine, "_mark_key_rate_limited") as mark_limited:
        rotated = engine._rotate_api_key(provider)

    assert rotated == "only-key"
    mark_limited.assert_not_called()


def test_rotate_api_key_marks_current_rotation_index(engine):
    provider = _setup_rotation_provider(engine, keys=["key-alpha", "key-beta", "key-gamma"])
    engine.provider_key_rotation[provider] = 2

    with (
        patch.object(engine, "_mark_key_rate_limited") as mark_limited,
        patch.object(engine, "_select_optimal_key", return_value=1),
    ):
        rotated = engine._rotate_api_key(provider)

    assert rotated == "key-beta"
    mark_limited.assert_called_once_with(provider, 2)


def test_roll_api_key_rolls_provider_with_two_keys(engine):
    provider = _setup_rotation_provider(engine, keys=["first-key", "second-key"])
    engine.provider_key_rotation[provider] = 0

    with patch.object(engine, "_rotate_api_key", return_value="second-key"):
        result = engine.roll_api_key(provider)

    assert "Rolled from key #0" in result
    assert "to key #0" in result
    assert "only" not in result.lower()


def test_request_with_key_rotation_calls_success_handler_with_provider(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]

    with (
        patch.object(engine, "_make_request", return_value=RequestResult(success=True, content="ok")),
        patch.object(engine, "_handle_provider_success") as handle_success,
    ):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])

    assert result.success is True
    handle_success.assert_called_once()
    assert handle_success.call_args.args[0] == provider
    assert 0 <= handle_success.call_args.args[1] < 5


def test_request_with_key_rotation_passes_failure_status_to_handler(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]

    with (
        patch.object(engine, "_make_request", return_value=RequestResult(success=False, error_message="quota", status_code=429)),
        patch.object(engine, "_handle_provider_failure") as handle_failure,
    ):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}], max_attempts=1)

    assert result.success is False
    handle_failure.assert_called_once_with(provider, "quota", 429)


def test_request_with_key_rotation_retries_quota_exceeded(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]
    calls = {"n": 0}

    def side_effect(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return RequestResult(success=False, error_message="quota_exceeded", status_code=400)
        return RequestResult(success=True, content="recovered")

    with patch.object(engine, "_make_request", side_effect=side_effect):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])

    assert result.success is True
    assert calls["n"] == 2


def test_handle_provider_failure_default_consecutive_failure_limit_is_five(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings.pop("consecutive_failure_limit", None)
    engine.consecutive_failures[provider] = 4

    with patch.object(engine, "_flag_provider") as flag_provider:
        engine._handle_provider_failure(provider, "internal server error", 500)

    assert engine.consecutive_failures[provider] == 5
    flag_provider.assert_any_call(provider, duration_minutes=30)


def test_roll_api_key_default_current_index_zero_in_message(engine):
    provider = _setup_rotation_provider(engine, keys=["first-secret-key", "second-secret-key"])
    engine.provider_key_rotation.pop(provider, None)

    with patch.object(engine, "_rotate_api_key", return_value="second-secret-key"):
        result = engine.roll_api_key(provider)

    assert "from key #0 (first-se...)" in result
    assert "second-s..." in result


def test_roll_api_key_current_index_bounds_excludes_equal_len(engine):
    provider = _setup_rotation_provider(engine, keys=["first-key", "second-key"])
    engine.provider_key_rotation[provider] = 2

    with patch.object(engine, "_rotate_api_key", return_value="second-key"):
        result = engine.roll_api_key(provider)

    assert "from key #2 (None)" in result


def test_request_with_key_rotation_exception_updates_failure_stats_and_handler(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]

    with (
        patch.object(engine, "_make_request", side_effect=RuntimeError("boom")),
        patch.object(engine, "_update_stats") as update_stats,
        patch.object(engine, "_handle_provider_failure") as handle_failure,
    ):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])

    assert result.success is False
    assert result.provider_used == provider
    assert result.response_time is not None
    assert 0 <= result.response_time < 5
    update_stats.assert_called_once()
    assert update_stats.call_args.args[0] == provider
    assert update_stats.call_args.args[1] is False
    assert 0 <= update_stats.call_args.args[2] < 5
    handle_failure.assert_called_once_with(provider, "boom", 0, None)


def test_handle_provider_failure_defaults_rotation_enabled_for_rate_limits(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings.pop("key_rotation_enabled", None)

    with (
        patch.object(engine, "_rotate_api_key", return_value="key-beta") as rotate,
        patch.object(engine, "_flag_key") as flag_key,
        patch.object(engine, "_flag_provider") as flag_provider,
    ):
        engine._handle_provider_failure(provider, "rate limit", 429)

    rotate.assert_called_once_with(provider)
    flag_key.assert_called_once_with(provider, "rate_limit")
    flag_provider.assert_not_called()


def test_handle_provider_failure_disabled_rotation_flags_provider_for_fifteen_minutes(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["key_rotation_enabled"] = False

    with (
        patch.object(engine, "_rotate_api_key") as rotate,
        patch.object(engine, "_flag_key") as flag_key,
        patch.object(engine, "_flag_provider") as flag_provider,
    ):
        engine._handle_provider_failure(provider, "rate limit", 429)

    rotate.assert_not_called()
    flag_key.assert_not_called()
    flag_provider.assert_called_once_with(provider, duration_minutes=15)


def test_handle_provider_failure_verbose_logs_rotation_message(engine_verbose):
    provider = _setup_rotation_provider(engine_verbose)
    with (
        patch.object(engine_verbose, "_rotate_api_key", return_value="key-beta"),
        patch("core.ai_engine.verbose_print") as verbose_print_mock,
    ):
        engine_verbose._handle_provider_failure(provider, "rate limit", 429)

    assert any(
        args[0] == f"🔑 Rotated {provider} API key due to rate_limit" and args[1] is True
        for args, _kwargs in verbose_print_mock.call_args_list
    )


def test_rotate_api_key_two_valid_keys_rotates(engine):
    provider = _setup_rotation_provider(engine, keys=["key-alpha", "key-beta"])
    engine.provider_key_rotation[provider] = 0

    with patch.object(engine, "_select_optimal_key", return_value=1):
        rotated = engine._rotate_api_key(provider)

    assert rotated == "key-beta"
    assert engine.provider_key_rotation[provider] == 1


def test_rotate_api_key_default_current_index_zero_when_missing(engine):
    provider = _setup_rotation_provider(engine, keys=["key-alpha", "key-beta", "key-gamma"])
    engine.provider_key_rotation.pop(provider, None)

    with (
        patch.object(engine, "_mark_key_rate_limited") as mark_limited,
        patch.object(engine, "_select_optimal_key", return_value=1),
    ):
        rotated = engine._rotate_api_key(provider)

    assert rotated == "key-beta"
    mark_limited.assert_called_once_with(provider, 0)


def test_select_optimal_key_resets_key_at_exact_cooldown_boundary(engine):
    provider = _setup_rotation_provider(engine)
    boundary = datetime.now() - timedelta(seconds=60)
    engine.key_usage_stats[provider]["key_0"]["rate_limited"] = True
    engine.key_usage_stats[provider]["key_0"]["last_used"] = boundary
    engine.key_usage_stats[provider]["key_1"]["rate_limited"] = True
    engine.key_usage_stats[provider]["key_1"]["last_used"] = datetime.now()
    engine.key_usage_stats[provider]["key_2"]["rate_limited"] = True
    engine.key_usage_stats[provider]["key_2"]["last_used"] = datetime.now()

    assert engine._select_optimal_key(provider) == 0
    assert engine.key_usage_stats[provider]["key_0"]["rate_limited"] is False


def test_select_optimal_key_verbose_logs_selected_key(engine_verbose):
    provider = _setup_rotation_provider(engine_verbose)

    with patch("core.ai_engine.verbose_print") as verbose_print_mock:
        selected = engine_verbose._select_optimal_key(provider)

    assert selected == 0
    verbose_print_mock.assert_called_once()
    args, _kwargs = verbose_print_mock.call_args
    assert args[0].startswith(f"🔑 Selected key #1 for {provider} (load score:")
    assert args[1] is True


def test_select_optimal_key_no_verbose_when_not_verbose(engine):
    provider = _setup_rotation_provider(engine)

    with patch("core.ai_engine.verbose_print") as verbose_print_mock:
        selected = engine._select_optimal_key(provider)

    assert selected == 0
    verbose_print_mock.assert_not_called()


def test_request_with_key_rotation_zero_attempts_returns_structured_failure(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]

    result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}], max_attempts=0)

    assert result.success is False
    assert result.error_message == "No request attempts made"
    assert result.error_type == "unknown"
    assert result.provider_used == provider


def test_request_with_key_rotation_exception_result_has_response_time(engine):
    provider = _setup_rotation_provider(engine)
    config = engine.providers[provider]

    with patch.object(engine, "_make_request", side_effect=RuntimeError("boom")):
        result = engine._request_with_key_rotation(provider, config, [{"role": "user", "content": "hi"}])

    assert result.success is False
    assert result.provider_used == provider
    assert result.response_time is not None
    assert 0 <= result.response_time < 5


def test_handle_provider_failure_uses_custom_consecutive_failure_limit(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["consecutive_failure_limit"] = 3
    engine.consecutive_failures[provider] = 2

    with patch.object(engine, "_flag_provider") as flag_provider:
        engine._handle_provider_failure(provider, "bad request", 400)

    flag_provider.assert_called_once_with(provider, duration_minutes=30)


def test_handle_provider_failure_verbose_logs_consecutive_failure_flag(engine_verbose):
    provider = _setup_rotation_provider(engine_verbose)
    engine_verbose.engine_settings["consecutive_failure_limit"] = 3
    engine_verbose.consecutive_failures[provider] = 2

    with patch("core.ai_engine.verbose_print") as verbose_print_mock:
        engine_verbose._handle_provider_failure(provider, "bad request", 400)

    assert any(
        args[0] == f"⚠️  {provider} flagged for 30min after 3 consecutive failures" and args[1] is True
        for args, _kwargs in verbose_print_mock.call_args_list
    )


def test_handle_provider_failure_unknown_errors_rotate_after_two_by_default(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings.pop("key_rotation_enabled", None)
    engine.consecutive_failures[provider] = 1

    with patch.object(engine, "_rotate_api_key", return_value="key-beta") as rotate:
        engine._handle_provider_failure(provider, "mystery failure", 418)

    rotate.assert_called_once_with(provider)


def test_handle_provider_failure_unknown_errors_respect_disabled_rotation(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["key_rotation_enabled"] = False
    engine.consecutive_failures[provider] = 1

    with patch.object(engine, "_rotate_api_key") as rotate:
        engine._handle_provider_failure(provider, "mystery failure", 418)

    rotate.assert_not_called()
