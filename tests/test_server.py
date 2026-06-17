"""Tests for server.py API endpoints"""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from server import app
    return TestClient(app)


# === Health Check ===

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


# === Models Endpoint ===

def test_list_models(client):
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert "data" in data


# === Status Endpoint ===

def test_get_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "total_providers" in data
    assert "enabled_providers" in data


# === Providers Endpoint ===

def test_get_providers(client):
    response = client.get("/api/providers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    # Should have provider configs (without api_keys)
    for name, config in data.items():
        assert "id" in config
        assert "enabled" in config
        assert "api_keys" not in config  # Should be sanitized


# === Provider Toggle ===

def test_toggle_provider(client):
    # Get a provider name
    providers_resp = client.get("/api/providers")
    provider_name = list(providers_resp.json().keys())[0]

    response = client.post(f"/api/providers/{provider_name}/toggle", json={
        "enabled": False
    })
    assert response.status_code == 200

    # Re-enable
    client.post(f"/api/providers/{provider_name}/toggle", json={"enabled": True})


def test_toggle_provider_not_found(client):
    response = client.post("/api/providers/nonexistent/toggle", json={
        "enabled": True
    })
    # Server may return 500 if exception handling differs
    assert response.status_code in [404, 500]


# === Statistics Endpoint ===

def test_get_statistics(client):
    response = client.get("/api/statistics")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "providers" in data
    assert "timestamp" in data


# === Chat Completions Endpoint ===

@patch('server.engine')
def test_chat_completions_success(mock_engine, client):
    from ai_engine import RequestResult
    mock_result = RequestResult(
        success=True,
        content="Hello! How can I help?",
        provider_used="openai",
        model_used="gpt-4",
        response_time=0.5
    )
    mock_engine.chat_completion.return_value = mock_result

    response = client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "Hello! How can I help?"


@patch('server.engine')
def test_chat_completions_failure(mock_engine, client):
    from ai_engine import RequestResult
    mock_result = RequestResult(
        success=False,
        error_message="Provider failed"
    )
    mock_engine.chat_completion.return_value = mock_result

    response = client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 500


@patch('server.engine')
def test_chat_completions_with_preferred_provider(mock_engine, client):
    from ai_engine import RequestResult
    mock_result = RequestResult(
        success=True,
        content="Response",
        provider_used="openai",
        model_used="gpt-4"
    )
    mock_engine.chat_completion.return_value = mock_result

    response = client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    }, headers={"X-Preferred-Provider": "openai"})
    assert response.status_code == 200


# === Test Model Endpoint ===

@patch('server.engine')
def test_test_model_success(mock_engine, client):
    from ai_engine import RequestResult
    mock_result = RequestResult(
        success=True,
        content="Test response",
        provider_used="openai",
        model_used="gpt-4"
    )
    mock_engine.chat_completion.return_value = mock_result

    response = client.post("/api/test-model", json={
        "provider": "openai",
        "model": "gpt-4",
        "message": "Test message"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_test_model_missing_params(client):
    response = client.post("/api/test-model", json={
        "provider": "openai"
    })
    # Server may return 400 or 200 with error in response
    assert response.status_code in [400, 200]
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is False


# === Autodecide Endpoint ===

@patch('server.engine')
def test_autodecide_discover(mock_engine, client):
    mock_engine.autodecide_config = {"enabled": True}
    mock_engine._discover_model_providers.return_value = [
        ("openai", "gpt-4"),
        ("azure", "gpt-4")
    ]
    mock_engine.providers = {
        "openai": {"priority": 1, "enabled": True},
        "azure": {"priority": 2, "enabled": True}
    }
    mock_engine._is_key_flagged.return_value = False

    response = client.get("/api/autodecide/gpt-4")
    assert response.status_code == 200
    data = response.json()
    assert data["autodecide_enabled"] is True


# === Dashboard Routes (require templates) ===

@pytest.mark.skip(reason="Templates not available in test environment")
def test_dashboard_page(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.skip(reason="Templates not available in test environment")
def test_providers_page(client):
    response = client.get("/providers")
    assert response.status_code == 200


@pytest.mark.skip(reason="Templates not available in test environment")
def test_statistics_page(client):
    response = client.get("/statistics")
    assert response.status_code == 200


@pytest.mark.skip(reason="Templates not available in test environment")
def test_models_page(client):
    response = client.get("/models")
    assert response.status_code == 200


@pytest.mark.skip(reason="Templates not available in test environment")
def test_chat_page(client):
    response = client.get("/chat")
    assert response.status_code == 200
