"""OpenAI-compatible API endpoint tests."""
import pytest


@pytest.mark.integration
def test_list_models_openai_format(server_client):
    resp = server_client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0
    assert "id" in data["data"][0]


@pytest.mark.integration
def test_chat_completion_via_test_harness(
    server_client, mock_provider_server, reset_server_test_harness_keys
):
    resp = server_client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hello"}],
        },
        headers={"X-Preferred-Provider": "test_harness"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    content = data["choices"][0]["message"]["content"]
    assert content == "alpha-ok"


@pytest.mark.integration
def test_chat_completion_stream_via_test_harness(
    server_client, mock_provider_server, reset_server_test_harness_keys
):
    resp = server_client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "stream hello"}],
            "stream": True,
        },
        headers={"X-Preferred-Provider": "test_harness"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    body = resp.text
    assert "data:" in body
    assert "[DONE]" in body


@pytest.mark.integration
def test_embeddings_stub_returns_placeholder_vector(server_client):
    resp = server_client.post(
        "/v1/embeddings",
        json={"model": "text-embedding-3-small", "input": "hello world"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    assert data["data"][0]["object"] == "embedding"
    assert len(data["data"][0]["embedding"]) == 1536
    assert data["usage"]["total_tokens"] > 0


@pytest.mark.integration
def test_embeddings_requires_input(server_client):
    resp = server_client.post("/v1/embeddings", json={"model": "text-embedding-3-small"})
    assert resp.status_code == 400
    assert "input is required" in resp.json()["error"]["message"]
