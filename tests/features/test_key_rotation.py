"""Integration tests for API key rotation against the mock provider server."""
import pytest

from core.provider_requests import RequestResult


@pytest.mark.integration
def test_auto_rotation_on_rate_limit(testing_engine, mock_provider_server):
    engine = testing_engine
    engine.engine_settings["key_rotation_enabled"] = True
    # Force use of beta key (rate-limited) then expect rotation to alpha
    engine.providers["test_harness"]["api_keys"] = [
        "test-key-beta",
        "test-key-alpha",
        "test-key-gamma",
    ]
    engine.provider_key_rotation["test_harness"] = 0
    result = engine.chat_completion(
        [{"role": "user", "content": "rotate me"}],
        provider="test_harness",
    )
    # Should succeed after rotating away from beta
    assert result.success is True
    assert engine.provider_key_rotation["test_harness"] != 0


@pytest.mark.integration
def test_auto_rotation_on_auth_error(testing_engine, mock_provider_server):
    engine = testing_engine
    engine.providers["test_harness"]["api_keys"] = [
        "test-key-gamma",
        "test-key-alpha",
        "test-key-beta",
    ]
    engine.provider_key_rotation["test_harness"] = 0
    result = engine.chat_completion(
        [{"role": "user", "content": "auth rotate"}],
        provider="test_harness",
    )
    assert result.success is True


@pytest.mark.integration
def test_manual_roll_key_endpoint(server_client, mock_provider_server):
    resp = server_client.post("/api/providers/test_harness/roll-key")
    assert resp.status_code == 200
    assert "Rolled" in resp.json()["message"] or "rolled" in resp.json()["message"].lower()


@pytest.mark.integration
def test_roll_key_single_key_provider(server_client):
    # Pick a provider with 1 key — should return no-op message
    resp = server_client.post("/api/providers/g4f/roll-key")
    assert resp.status_code == 200
    message = resp.json()["message"].lower()
    assert "only" in message or "one key" in message


@pytest.mark.integration
def test_forced_provider_server_error_does_not_succeed(testing_engine, mock_provider_server):
    engine = testing_engine
    engine.engine_settings["key_rotation_enabled"] = True
    engine.providers["test_harness"]["api_keys"] = [
        "test-key-alpha",
        "test-key-beta",
        "test-key-gamma",
    ]
    attempts = {"count": 0}

    def failing_make_request(provider_name, config, messages, model=None, **kwargs):
        attempts["count"] += 1
        return RequestResult(
            success=False,
            error_message="internal server error",
            status_code=500,
            error_type="server_error",
        )

    engine._make_request = failing_make_request
    result = engine.chat_completion(
        [{"role": "user", "content": "fail"}],
        provider="test_harness",
    )
    assert result.success is False
    assert result.status_code == 500
    assert attempts["count"] == 1
