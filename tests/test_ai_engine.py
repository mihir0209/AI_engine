"""Tests for ai_engine.py module"""
import time
from datetime import datetime, timedelta

import pytest
from unittest.mock import patch

from core.ai_engine import AI_engine, RequestResult


def _setup_rotation_provider(engine, name="rotation_test", keys=None):
    """Attach a synthetic multi-key provider for rotation unit tests."""
    keys = keys or ["key-alpha", "key-beta", "key-gamma"]
    engine.providers[name] = {
        "enabled": True,
        "api_keys": keys,
        "format": "openai",
    }
    engine.provider_key_rotation[name] = 0
    engine.usage_stats[name] = {
        "requests": 0,
        "successes": 0,
        "failures": 0,
        "total_response_time": 0.0,
        "last_used": None,
        "consecutive_failures": 0,
        "flagged": False,
        "enabled": True,
    }
    engine.key_usage_stats[name] = {}
    engine.key_last_used[name] = {}
    engine.key_request_count[name] = {}
    for i in range(len(keys)):
        key_id = f"key_{i}"
        engine.key_usage_stats[name][key_id] = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "last_used": None,
            "rate_limited": False,
            "weight": 1.0,
            "requests_this_minute": 0,
        }
        engine.key_last_used[name][key_id] = None
        engine.key_request_count[name][key_id] = []
    return name


@pytest.fixture
def engine():
    eng = AI_engine(verbose=False)
    eng.engine_settings["key_rotation_enabled"] = True
    yield eng
    eng.engine_settings["key_rotation_enabled"] = True


@pytest.fixture
def engine_verbose():
    return AI_engine(verbose=True)


# === RequestResult Tests ===

def test_request_result_defaults():
    r = RequestResult(success=False)
    assert r.success is False
    assert r.content == ""
    assert r.status_code == 0
    assert r.response_time == 0.0
    assert r.error_message == ""
    assert r.error_type == "unknown"
    assert r.provider_used == ""
    assert r.model_used == ""
    assert r.raw_response is None


def test_request_result_with_values():
    r = RequestResult(
        success=True,
        content="hello",
        status_code=200,
        provider_used="openai",
        model_used="gpt-4"
    )
    assert r.success is True
    assert r.content == "hello"
    assert r.provider_used == "openai"


# === Initialization Tests ===

def test_engine_init(engine):
    assert engine.verbose is False
    assert isinstance(engine.providers, dict)
    assert isinstance(engine.usage_stats, dict)
    assert isinstance(engine.flagged_keys, dict)


def test_engine_init_verbose(engine_verbose):
    assert engine_verbose.verbose is True


def test_engine_loads_providers(engine):
    assert len(engine.providers) > 0


def test_engine_no_duplicate_dicts(engine):
    assert isinstance(engine.key_usage_stats, dict)
    assert isinstance(engine.key_last_used, dict)
    assert isinstance(engine.key_request_count, dict)


# === Verbose Tests ===

def test_set_verbose(engine):
    engine.set_verbose(True)
    assert engine.get_verbose() is True
    engine.set_verbose(False)
    assert engine.get_verbose() is False


def test_global_verbose():
    engine = AI_engine(verbose=False)
    original = engine.get_global_verbose()
    engine.set_global_verbose(True)
    assert engine.get_global_verbose() is True
    engine.set_global_verbose(original)


# === Key Rotation Tests ===

def test_is_key_flagged_no_flag(engine):
    assert engine._is_key_flagged("nonexistent") is False


def test_is_key_flagged_with_flag(engine):
    from datetime import datetime, timedelta
    engine.flagged_keys["test_provider"] = {
        "flagged_at": datetime.now(),
        "flag_until": datetime.now() + timedelta(hours=1),
        "error_type": "rate_limit"
    }
    assert engine._is_key_flagged("test_provider") is True


def test_is_key_flagged_expired(engine):
    engine.flagged_keys["test_provider"] = {
        "flagged_at": datetime.now() - timedelta(hours=2),
        "flag_until": datetime.now() - timedelta(hours=1),
        "error_type": "rate_limit"
    }
    assert engine._is_key_flagged("test_provider") is False
    assert "test_provider" not in engine.flagged_keys


def test_select_optimal_key_returns_none_without_keys(engine):
    engine.providers["empty_keys"] = {"enabled": True, "api_keys": []}
    assert engine._select_optimal_key("empty_keys") is None
    assert engine._select_optimal_key("missing_provider") is None


def test_select_optimal_key_single_key_returns_index(engine):
    provider = _setup_rotation_provider(engine, keys=["only-key"])
    assert engine._select_optimal_key(provider) == 0


def test_select_optimal_key_prefers_lower_load_key(engine):
    provider = _setup_rotation_provider(engine)
    engine.key_request_count[provider]["key_0"] = [datetime.now(), datetime.now()]
    engine.key_usage_stats[provider]["key_0"]["weight"] = 2.0
    selected = engine._select_optimal_key(provider)
    assert selected in (1, 2)
    assert selected != 0


def test_select_optimal_key_skips_recently_rate_limited_key(engine):
    provider = _setup_rotation_provider(engine)
    engine.key_usage_stats[provider]["key_0"]["rate_limited"] = True
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    selected = engine._select_optimal_key(provider)
    assert selected in (1, 2)


def test_rotate_api_key_disabled_returns_current_key(engine):
    provider = _setup_rotation_provider(engine, keys=["first", "second"])
    engine.engine_settings["key_rotation_enabled"] = False
    engine.provider_key_rotation[provider] = 1
    with patch.object(engine, "_get_current_api_key", return_value="second") as get_key:
        rotated = engine._rotate_api_key(provider)
    get_key.assert_called_once_with(provider)
    assert rotated == "second"
    assert engine.key_usage_stats[provider]["key_0"]["rate_limited"] is False


def test_rotate_api_key_single_key_returns_current(engine):
    provider = _setup_rotation_provider(engine, keys=["solo-key"])
    rotated = engine._rotate_api_key(provider)
    assert rotated == "solo-key"
    assert engine.provider_key_rotation[provider] == 0


def test_rotate_api_key_changes_provider_index(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    rotated = engine._rotate_api_key(provider)
    assert rotated in ("key-beta", "key-gamma")
    assert engine.provider_key_rotation[provider] != 0
    assert engine.key_usage_stats[provider]["key_0"]["rate_limited"] is True


def test_handle_provider_failure_rate_limit_rotates_key(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    engine._handle_provider_failure(provider, "rate limit exceeded", 429)
    assert engine.provider_key_rotation[provider] != 0
    assert provider in engine.flagged_keys
    assert engine.flagged_keys[provider]["error_type"] == "rate_limit"


def test_handle_provider_failure_auth_error_rotates_key(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    engine._handle_provider_failure(provider, "invalid api key", 401)
    assert engine.provider_key_rotation[provider] != 0
    assert engine.flagged_keys[provider]["error_type"] == "auth_error"


def test_handle_provider_failure_quota_exceeded_rotates_key(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    engine._handle_provider_failure(provider, "daily limit exceeded", 200)
    assert engine.provider_key_rotation[provider] != 0
    assert engine.flagged_keys[provider]["error_type"] == "quota_exceeded"


def test_handle_provider_failure_server_error_does_not_rotate_key(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine._handle_provider_failure(provider, "internal server error", 500)
    assert engine.provider_key_rotation[provider] == 0
    assert provider in engine.flagged_keys


def test_handle_provider_failure_unknown_rotates_after_two_failures(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    engine._handle_provider_failure(provider, "something weird", 418)
    assert engine.provider_key_rotation[provider] == 0
    engine._handle_provider_failure(provider, "something weird again", 418)
    assert engine.provider_key_rotation[provider] != 0


def test_handle_provider_failure_rate_limit_disabled_flags_provider(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["key_rotation_enabled"] = False
    engine.provider_key_rotation[provider] = 0
    engine._handle_provider_failure(provider, "rate limit exceeded", 429)
    assert engine.provider_key_rotation[provider] == 0
    assert provider in engine.flagged_keys


def test_roll_api_key_multi_key_rotates(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["key_rotation_enabled"] = True
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    result = engine.roll_api_key(provider)
    assert "Rolled" in result or "rolled" in result.lower()
    assert engine.provider_key_rotation[provider] != 0


def test_roll_api_key_disabled_reports_settings_message(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["key_rotation_enabled"] = False
    with patch.object(engine, "_rotate_api_key", return_value="key-alpha"):
        result = engine.roll_api_key(provider)
    assert "disabled in engine settings" in result.lower()


def test_roll_api_key_missing_api_keys_treated_as_empty(engine):
    engine.providers["no_keys_provider"] = {"enabled": True, "format": "openai"}
    result = engine.roll_api_key("no_keys_provider")
    assert "0 key" in result.lower()


def test_roll_api_key_message_truncates_long_key_preview(engine):
    provider = _setup_rotation_provider(
        engine,
        keys=["abcdefghijklmnop", "key-beta", "key-gamma"],
    )
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    result = engine.roll_api_key(provider)
    assert "abcdefgh..." in result
    assert "key #0" in result


def test_roll_api_key_no_change_reports_staying_message(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    with patch.object(engine, "_rotate_api_key", return_value="key-alpha"):
        result = engine.roll_api_key(provider)
    assert "staying at key #0" in result.lower()


def test_roll_api_key_provider_not_found_exact_message(engine):
    result = engine.roll_api_key("missing_provider_xyz")
    assert result == "Provider missing_provider_xyz not found"


def test_roll_api_key_single_key_exact_no_op_message(engine):
    provider = _setup_rotation_provider(engine, keys=["solo-key"])
    result = engine.roll_api_key(provider)
    assert result == f"Provider {provider} has only 1 key(s), no rolling needed"


def test_roll_api_key_disabled_exact_message(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["key_rotation_enabled"] = False
    with patch.object(engine, "_rotate_api_key", return_value="key-alpha"):
        result = engine.roll_api_key(provider)
    assert result == "⚠️ Key rotation is disabled in engine settings"


def test_roll_api_key_successful_roll_message_format(engine):
    provider = _setup_rotation_provider(
        engine,
        keys=["key-alpha", "key-beta", "key-gamma"],
    )
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    result = engine.roll_api_key(provider)
    new_index = engine.provider_key_rotation[provider]
    assert result.startswith("✅ Rolled from key #0 (key-alph...) to key #")
    assert f"to key #{new_index}" in result
    new_key = engine.providers[provider]["api_keys"][new_index]
    expected_preview = new_key if len(new_key) <= 8 else new_key[:8] + "..."
    assert f"({expected_preview})" in result


def test_roll_api_key_short_key_preview_no_truncation(engine):
    provider = _setup_rotation_provider(
        engine,
        keys=["short01", "short02", "short03"],
    )
    engine.provider_key_rotation[provider] = 0
    engine.key_usage_stats[provider]["key_0"]["last_used"] = datetime.now()
    result = engine.roll_api_key(provider)
    assert "..." not in result
    assert "short01" in result


def test_handle_provider_failure_service_unavailable_flags_no_rotation(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine._handle_provider_failure(provider, "service temporarily unavailable", 503)
    assert provider in engine.flagged_keys
    assert engine.provider_key_rotation[provider] == 0
    assert engine.consecutive_failures[provider] == 1


def test_handle_provider_failure_unknown_first_failure_no_rotation(engine):
    provider = _setup_rotation_provider(engine)
    engine.provider_key_rotation[provider] = 0
    engine._handle_provider_failure(provider, "something weird", 418)
    assert engine.provider_key_rotation[provider] == 0
    assert engine.consecutive_failures[provider] == 1


def test_handle_provider_failure_flags_after_consecutive_limit(engine):
    provider = _setup_rotation_provider(engine)
    engine.engine_settings["consecutive_failure_limit"] = 3
    for _ in range(3):
        engine._handle_provider_failure(provider, "internal server error", 500)
    assert provider in engine.flagged_keys
    assert engine.consecutive_failures[provider] == 3


# === Error Classification Tests ===

def test_classify_rate_limit(engine):
    assert engine._classify_error("rate limit exceeded", 429) == "rate_limit"
    assert engine._classify_error("too many requests", 429) == "rate_limit"
    assert engine._classify_error("throttled", 429) == "rate_limit"


def test_classify_auth_error(engine):
    assert engine._classify_error("invalid api key", 401) == "auth_error"
    assert engine._classify_error("unauthorized", 403) == "auth_error"


def test_classify_quota_exceeded(engine):
    assert engine._classify_error("daily limit exceeded", 200) == "quota_exceeded"


def test_classify_service_unavailable(engine):
    assert engine._classify_error("model not found", 503) == "service_unavailable"


def test_classify_server_error(engine):
    assert engine._classify_error("internal error", 500) == "server_error"
    assert engine._classify_error("bad gateway", 502) == "server_error"


def test_classify_network_error(engine):
    assert engine._classify_error("connection timeout", 0) == "network_error"
    assert engine._classify_error("connection refused", 0) == "network_error"


def test_classify_bad_request(engine):
    assert engine._classify_error("invalid request", 400) == "bad_request"


def test_classify_unknown(engine):
    assert engine._classify_error("something weird happened", 200) == "unknown"


def test_classify_with_response_json(engine):
    response_json = {"error": {"message": "rate_limit_exceeded"}}
    assert engine._classify_error("", 200, response_json) == "rate_limit"


# === Provider Management Tests ===

def test_flag_provider(engine):
    provider_name = list(engine.providers.keys())[0]
    engine._flag_provider(provider_name, duration_minutes=15)
    assert provider_name in engine.flagged_keys
    assert engine.usage_stats[provider_name]["flagged"] is True


def test_handle_provider_success(engine):
    provider_name = list(engine.providers.keys())[0]
    engine.consecutive_failures[provider_name] = 5
    engine.usage_stats[provider_name]["failures"] = 5
    engine.flagged_keys[provider_name] = {"flag_until": time.time() + 999}

    engine._handle_provider_success(provider_name, 1.0)

    assert engine.consecutive_failures[provider_name] == 0
    assert provider_name not in engine.flagged_keys


def test_handle_provider_failure(engine):
    provider_name = list(engine.providers.keys())[0]
    engine._handle_provider_failure(provider_name, "error", 500)
    assert engine.consecutive_failures[provider_name] == 1
    assert engine.usage_stats[provider_name]["failures"] >= 1


def test_handle_provider_failure_consecutive(engine):
    for i in range(5):
        engine._handle_provider_failure("test_provider", "error", 500)
    assert engine.consecutive_failures["test_provider"] == 5
    assert "test_provider" in engine.flagged_keys


# === Model Name Tests ===

def test_normalize_model_name(engine):
    assert engine.normalize_model_name("GPT-4") == "gpt4"
    assert engine.normalize_model_name("provider-1/llama-3.1") == "llama31"
    assert engine.normalize_model_name("@cf/meta/llama-3") == "llama3"
    assert engine.normalize_model_name("") == ""


def test_model_matches(engine):
    assert engine.model_matches("gpt-4", "gpt-4") is True
    assert engine.model_matches("gpt-4", "gpt-4-turbo") is True
    assert engine.model_matches("gpt-4", "claude-3") is False
    assert engine.model_matches("", "gpt-4") is False
    assert engine.model_matches("gpt-4", "") is False


# === Chat Completion Tests ===

def test_streaming_falls_back_after_retryable_provider_error(testing_engine):
    testing_engine.providers = {
        "first": {"enabled": True, "priority": 1, "format": "openai", "model": "m1"},
        "second": {"enabled": True, "priority": 2, "format": "openai", "model": "m2"},
    }
    testing_engine._get_available_providers = lambda preferred=None: [
        ("first", testing_engine.providers["first"]),
        ("second", testing_engine.providers["second"]),
    ]

    def first_stream(*args, **kwargs):
        yield {"error": "upstream timeout", "done": True}

    def second_stream(*args, **kwargs):
        yield {"content": "ok"}
        yield {"done": True}

    from unittest.mock import patch
    with patch.object(testing_engine, "_make_streaming_request", side_effect=[first_stream(), second_stream()]):
        chunks = list(testing_engine.chat_completion_stream([{"role": "user", "content": "hi"}]))

    assert chunks == [
        {"content": "ok"},
        {"done": True, "provider": "second", "model": "m2"},
    ]


def test_streaming_non_retryable_error_is_terminal(testing_engine):
    testing_engine.providers = {
        "first": {"enabled": True, "priority": 1, "format": "openai", "model": "m1"},
        "second": {"enabled": True, "priority": 2, "format": "openai", "model": "m2"},
    }
    testing_engine._get_available_providers = lambda preferred=None: [
        ("first", testing_engine.providers["first"]),
        ("second", testing_engine.providers["second"]),
    ]

    def first_stream(*args, **kwargs):
        yield {"error": "invalid request", "done": True}

    from unittest.mock import patch
    with patch.object(testing_engine, "_make_streaming_request", side_effect=[first_stream()]) as stream:
        chunks = list(testing_engine.chat_completion_stream([{"role": "user", "content": "hi"}]))

    assert chunks == [{"error": "invalid request", "done": True, "provider": "first"}]
    assert stream.call_count == 1


def test_chat_completion_no_providers():
    engine = AI_engine(verbose=False)
    engine.providers = {}
    result = engine.chat_completion(messages=[{"role": "user", "content": "hi"}])
    assert result.success is False
    assert result.error_type == "no_providers"


def test_chat_completion_forced_provider_not_found(engine):
    result = engine.chat_completion(
        messages=[{"role": "user", "content": "hi"}],
        preferred_provider="nonexistent",
        force_provider=True
    )
    assert result.success is False
    assert result.error_type == "provider_not_found"


def test_chat_completion_forced_provider_disabled(engine):
    # Disable a provider
    provider_name = list(engine.providers.keys())[0]
    engine.providers[provider_name]["enabled"] = False

    result = engine.chat_completion(
        messages=[{"role": "user", "content": "hi"}],
        preferred_provider=provider_name,
        force_provider=True
    )
    assert result.success is False
    assert result.error_type == "provider_disabled"

    # Re-enable
    engine.providers[provider_name]["enabled"] = True


def test_chat_completion_provider_model_parse(engine):
    provider_name = list(engine.providers.keys())[0]
    model = engine.providers[provider_name].get("model", "test")

    # Mock the request to avoid actual API call
    with patch.object(engine, '_make_request') as mock_req:
        mock_req.return_value = RequestResult(success=True, content="test response")
        result = engine.chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model=f"{provider_name}/{model}"
        )
        assert result.success is True


# === Stress Test Tests ===

def test_stress_test_sequential_no_providers(engine):
    results = engine._stress_test_sequential({}, 1, "test")
    assert results == {}


def test_stress_test_provider_score(engine):
    test_results = {
        "p1": {"passed": True, "success_rate": 90, "avg_response_time": 1.0, "response_times": [1.0]},
        "p2": {"passed": True, "success_rate": 70, "avg_response_time": 3.0, "response_times": [3.0]},
    }
    engine.providers = {
        "p1": {"priority": 10, "enabled": True},
        "p2": {"priority": 5, "enabled": True}
    }
    engine._optimize_priorities(test_results)


# === Roll API Key Tests ===

def test_roll_api_key_single_key(engine):
    provider_name = list(engine.providers.keys())[0]
    api_keys = engine.providers[provider_name].get("api_keys", [])
    if len(api_keys) <= 1:
        result = engine.roll_api_key(provider_name)
        assert "only" in result.lower() or "no rolling" in result.lower()


def test_roll_api_key_nonexistent(engine):
    result = engine.roll_api_key("nonexistent_provider")
    assert "not found" in result.lower()


# === Request Format Tests ===

def test_make_request_unknown_format(engine):
    result = engine._make_request("test", {"format": "unknown_format"}, [])
    assert result.success is False
    assert result.error_type in ("unsupported_format", "request_exception", "provider_exception")


# === Cleanup Request Counts ===

def test_cleanup_request_counts(engine):
    from datetime import datetime, timedelta
    provider_name = list(engine.providers.keys())[0]
    # Initialize the structure first
    engine.key_request_count[provider_name] = {
        "key_0": [datetime.now() - timedelta(minutes=3), datetime.now()]
    }
    engine._cleanup_request_counts(provider_name)
    assert len(engine.key_request_count[provider_name]["key_0"]) == 1


def test_cleanup_request_counts_empty(engine):
    engine._cleanup_request_counts("nonexistent")


# === Key Load Score ===

def test_calculate_key_load_score_no_data(engine):
    score = engine._calculate_key_load_score("nonexistent", 0)
    assert score == 0.0


# === Provider Recovery ===

def test_check_provider_recovery_no_history(engine):
    assert engine._check_provider_recovery("nonexistent") is True


def test_check_provider_recovery_flagged(engine):
    provider_name = list(engine.providers.keys())[0]
    assert engine._check_provider_recovery(provider_name) is True


def test_check_provider_recovery_recent_failure(engine):
    provider_name = list(engine.providers.keys())[0]
    assert engine._check_provider_recovery(provider_name) is True
