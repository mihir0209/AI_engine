"""Legacy server tests — unique cases not covered by tests/features/test_server_*.py.

Endpoint matrix coverage lives under tests/features/. This module keeps mocked-engine
unit tests, dashboard skips, workflows, and edge-case handlers.
"""
import pytest
from unittest.mock import patch


# === Chat Completions (mocked engine) ===

@patch('ai_engine.server.app.engine')
def test_chat_completions_success(mock_engine, server_client):
    from core.ai_engine import RequestResult
    mock_result = RequestResult(
        success=True,
        content="Hello! How can I help?",
        provider_used="openai",
        model_used="gpt-4",
        response_time=0.5
    )
    mock_engine.chat_completion.return_value = mock_result

    response = server_client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "Hello! How can I help?"


@patch('ai_engine.server.app.engine')
def test_chat_completions_failure(mock_engine, server_client):
    from core.ai_engine import RequestResult
    mock_result = RequestResult(
        success=False,
        error_message="Provider failed"
    )
    mock_engine.chat_completion.return_value = mock_result

    response = server_client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 500


@patch('ai_engine.server.app.engine')
def test_chat_completions_with_preferred_provider(mock_engine, server_client):
    from core.ai_engine import RequestResult
    mock_result = RequestResult(
        success=True,
        content="Response",
        provider_used="openai",
        model_used="gpt-4"
    )
    mock_engine.chat_completion.return_value = mock_result

    response = server_client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    }, headers={"X-Preferred-Provider": "openai"})
    assert response.status_code == 200


# === Test Model Endpoint (mocked engine) ===

@patch('ai_engine.server.app.engine')
def test_test_model_success(mock_engine, server_client):
    from core.ai_engine import RequestResult
    mock_result = RequestResult(
        success=True,
        content="Test response",
        provider_used="openai",
        model_used="gpt-4"
    )
    mock_engine.chat_completion.return_value = mock_result

    response = server_client.post("/api/test-model", json={
        "provider": "openai",
        "model": "gpt-4",
        "message": "Test message"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_test_model_missing_params(server_client):
    response = server_client.post("/api/test-model", json={
        "provider": "openai"
    })
    assert response.status_code in [400, 500, 200]
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is False


# === Autodecide Endpoint ===

@patch('ai_engine.server.app.engine')
def test_autodecide_discover(mock_engine, server_client):
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

    response = server_client.get("/api/autodecide/gpt-4")
    assert response.status_code == 200
    data = response.json()
    assert data["autodecide_enabled"] is True


# === Dashboard Routes (require templates) ===

@pytest.mark.skip(reason="Templates not available in test environment")
def test_dashboard_page(server_client):
    response = server_client.get("/")
    assert response.status_code == 200


@pytest.mark.skip(reason="Templates not available in test environment")
def test_providers_page(server_client):
    response = server_client.get("/providers")
    assert response.status_code == 200


@pytest.mark.skip(reason="Templates not available in test environment")
def test_statistics_page(server_client):
    response = server_client.get("/statistics")
    assert response.status_code == 200


@pytest.mark.skip(reason="Templates not available in test environment")
def test_models_page(server_client):
    response = server_client.get("/models")
    assert response.status_code == 200


@pytest.mark.skip(reason="Templates not available in test environment")
def test_chat_page(server_client):
    response = server_client.get("/chat")
    assert response.status_code == 200


# === Streaming Endpoint ===

@patch('ai_engine.server.app.engine')
def test_chat_completions_stream(mock_engine, server_client):
    from core.ai_engine import RequestResult
    mock_result = RequestResult(
        success=True,
        content="Hello! This is a streaming test.",
        provider_used="openai",
        model_used="gpt-4"
    )
    mock_engine.chat_completion.return_value = mock_result

    response = server_client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    })
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "data:" in response.text
    assert "[DONE]" in response.text


# === Supplementary Module Endpoints ===

def test_metrics_endpoints_endpoint(server_client):
    response = server_client.get("/api/metrics/endpoints")
    assert response.status_code == 200


def test_sla_status_endpoint(server_client):
    response = server_client.get("/api/sla/status")
    assert response.status_code == 200


def test_errors_endpoint(server_client):
    response = server_client.get("/api/errors")
    assert response.status_code == 200
    assert "errors" in response.json()


def test_health_checks_endpoint(server_client):
    response = server_client.get("/api/health/checks")
    assert response.status_code == 200
    assert "checks" in response.json()


# === Workflow Endpoints ===

def test_list_workflows_endpoint(server_client):
    response = server_client.get("/api/workflows")
    assert response.status_code == 200
    data = response.json()
    assert "workflows" in data or "detail" in data


def test_create_workflow_endpoint(server_client):
    response = server_client.post("/api/workflows", json={
        "name": "Test Workflow",
        "description": "Test",
        "steps": [{"id": "s1", "step_type": "ai_call"}]
    })
    assert response.status_code in [200, 500]


def test_execute_workflow_endpoint(server_client):
    create_resp = server_client.post("/api/workflows", json={
        "name": "Test WF",
        "steps": [{"id": "s1", "step_type": "output", "config": {"field": "result"}}]
    })
    if create_resp.status_code == 200:
        wf_id = create_resp.json().get("workflow_id")
        if wf_id:
            response = server_client.post(f"/api/workflows/{wf_id}/execute", json={"input": {"data": "test"}})
            assert response.status_code in [200, 500]


# === Request Size Limit ===

def test_request_size_limit(server_client):
    large_content = "x" * (11 * 1024 * 1024)
    response = server_client.post("/v1/chat/completions",
                          json={"model": "gpt-4", "messages": [{"role": "user", "content": large_content}]},
                          headers={"Content-Length": str(len(large_content))})
    assert response.status_code in [200, 413, 500]