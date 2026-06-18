"""Tests for chat_module/router.py"""
import pytest
from fastapi.testclient import TestClient

from chat_module.router import router


@pytest.fixture
def client(tmp_path):
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def chat_db(client):
    """Create a fresh database for each test"""
    from chat_module.router import chat_db as db
    return db


# === Chat CRUD Tests ===

def test_create_chat(client):
    response = client.post("/api/chat/chats", json={
        "title": "Test Chat",
        "model": "gpt-4",
        "provider": "openai"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["chat_id"] > 0


def test_create_temporary_chat(client):
    response = client.post("/api/chat/chats", json={
        "title": "Temp Chat",
        "is_temporary": True,
        "temporary_timer_minutes": 10
    })
    assert response.status_code == 200
    data = response.json()
    assert data["chat"]["is_temporary"] is True


def test_create_chat_validation_error(client):
    response = client.post("/api/chat/chats", json={
        "title": ""  # Empty title
    })
    assert response.status_code == 422


def test_get_chats(client):
    client.post("/api/chat/chats", json={"title": "Chat 1"})
    client.post("/api/chat/chats", json={"title": "Chat 2"})
    response = client.get("/api/chat/chats")
    assert response.status_code == 200
    chats = response.json()
    assert len(chats) >= 2


def test_get_chats_with_limit(client):
    for i in range(5):
        client.post("/api/chat/chats", json={"title": f"Chat {i}"})
    response = client.get("/api/chat/chats?limit=3")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_get_chat(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    response = client.get(f"/api/chat/chats/{chat_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["chat"]["title"] == "Test"


def test_get_chat_not_found(client):
    response = client.get("/api/chat/chats/99999")
    assert response.status_code == 404


def test_update_chat(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Original"})
    chat_id = create_resp.json()["chat_id"]
    response = client.put(f"/api/chat/chats/{chat_id}", json={"title": "Updated"})
    assert response.status_code == 200
    assert response.json()["chat"]["title"] == "Updated"


def test_delete_chat(client):
    create_resp = client.post("/api/chat/chats", json={"title": "To Delete"})
    chat_id = create_resp.json()["chat_id"]
    response = client.delete(f"/api/chat/chats/{chat_id}")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_delete_chat_not_found(client):
    response = client.delete("/api/chat/chats/99999")
    assert response.status_code == 404


# === Message Tests ===

def test_send_message(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    response = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user",
        "content": "Hello"
    })
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_send_system_message(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    response = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system",
        "content": "You are a helpful assistant"
    })
    assert response.status_code == 200


def test_send_message_invalid_role(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    response = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "invalid",
        "content": "Hello"
    })
    assert response.status_code == 422


def test_send_message_empty_content(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    response = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user",
        "content": ""
    })
    assert response.status_code == 422


def test_send_message_chat_not_found(client):
    response = client.post("/api/chat/chats/99999/messages", json={
        "role": "user",
        "content": "Hello"
    })
    assert response.status_code == 404


def test_get_messages(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })
    response = client.get(f"/api/chat/chats/{chat_id}/messages")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_messages_with_after_id(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    # Send a system message (doesn't trigger AI response)
    msg1_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "System prompt"
    })
    msg1_id = msg1_resp.json()["message_id"]
    # Send another system message
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "Another system message"
    })
    response = client.get(f"/api/chat/chats/{chat_id}/messages?after_id={msg1_id}")
    assert response.status_code == 200
    assert len(response.json()) == 1


# === Convert to Permanent ===

def test_convert_to_permanent(client):
    create_resp = client.post("/api/chat/chats", json={
        "title": "Temp",
        "is_temporary": True
    })
    chat_id = create_resp.json()["chat_id"]
    response = client.post(f"/api/chat/chats/{chat_id}/convert-to-permanent")
    assert response.status_code == 200
    assert response.json()["chat"]["is_temporary"] is False


def test_convert_already_permanent(client):
    create_resp = client.post("/api/chat/chats", json={
        "title": "Perm",
        "is_temporary": False
    })
    chat_id = create_resp.json()["chat_id"]
    response = client.post(f"/api/chat/chats/{chat_id}/convert-to-permanent")
    assert response.status_code == 400


# === Stats ===

def test_get_stats(client):
    response = client.get("/api/chat/stats")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "stats" in response.json()
