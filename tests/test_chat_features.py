"""Tests for new chat features: edit, regenerate, search, export"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from fastapi import FastAPI
    from chat_module.router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# === Message Editing Tests ===

def test_edit_message(client):
    # Create chat and message
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    msg_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Original content"
    })
    message_id = msg_resp.json()["message_id"]

    # Edit the message
    response = client.put(f"/api/chat/messages/{message_id}", json={
        "content": "Edited content"
    })
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["message"]["content"] == "Edited content"


def test_edit_message_not_found(client):
    response = client.put("/api/chat/messages/99999", json={
        "content": "New content"
    })
    assert response.status_code == 404


def test_edit_message_empty_content(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    msg_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Original"
    })
    message_id = msg_resp.json()["message_id"]

    response = client.put(f"/api/chat/messages/{message_id}", json={
        "content": ""
    })
    assert response.status_code == 422  # Validation error


# === Regenerate Tests ===

def test_regenerate_response(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    msg_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })
    message_id = msg_resp.json()["message_id"]

    response = client.post(f"/api/chat/chats/{chat_id}/regenerate/{message_id}")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_regenerate_from_assistant_message(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    # Add assistant message directly (bypass user message check)
    msg_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "System prompt"
    })
    message_id = msg_resp.json()["message_id"]

    response = client.post(f"/api/chat/chats/{chat_id}/regenerate/{message_id}")
    assert response.status_code == 400  # Can only regenerate from user messages


def test_regenerate_chat_not_found(client):
    response = client.post("/api/chat/chats/99999/regenerate/1")
    assert response.status_code == 404


# === Search Tests ===

def test_search_messages(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello world"
    })
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Goodbye world"
    })
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Something else"
    })

    response = client.post("/api/chat/search", json={
        "query": "world"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] >= 2  # At least two messages contain "world"


def test_search_messages_specific_chat(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "unique_term"
    })

    response = client.post("/api/chat/search", json={
        "query": "unique_term",
        "chat_id": chat_id
    })
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_no_results(client):
    response = client.post("/api/chat/search", json={
        "query": "nonexistent_term_xyz"
    })
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_search_empty_query(client):
    response = client.post("/api/chat/search", json={
        "query": ""
    })
    assert response.status_code == 422


# === Export Tests ===

def test_export_markdown(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test Chat"})
    chat_id = create_resp.json()["chat_id"]
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "Hi there!"
    })

    response = client.get(f"/api/chat/chats/{chat_id}/export?format=markdown")
    assert response.status_code == 200
    data = response.json()
    assert "export" in data
    assert "Test Chat" in data["export"]
    assert "Hello" in data["export"]


def test_export_json(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test Chat"})
    chat_id = create_resp.json()["chat_id"]
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })

    response = client.get(f"/api/chat/chats/{chat_id}/export?format=json")
    assert response.status_code == 200
    data = response.json()
    assert "chat" in data
    assert "messages" in data
    assert data["chat"]["title"] == "Test Chat"


def test_export_chat_not_found(client):
    response = client.get("/api/chat/chats/99999/export")
    assert response.status_code == 404
