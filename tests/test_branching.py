"""Tests for branching and provider health features"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from fastapi import FastAPI
    from chat_module.router import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        return client


# === Branching Tests ===

def _add_user_msg(client, chat_id, content):
    """Add a user message that won't trigger AI processing (by also adding system response)"""
    resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": content
    })
    msg_id = resp.json()["message_id"]
    # Add system response to prevent background AI processing from blocking
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": f"Response to: {content}"
    })
    return msg_id


def test_create_branch(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Branch Test"})
    chat_id = create_resp.json()["chat_id"]

    msg1_id = _add_user_msg(client, chat_id, "Message 1")
    msg3_id = _add_user_msg(client, chat_id, "Message 3")

    # Create branch from message 3
    response = client.post(f"/api/chat/chats/{chat_id}/branch/{msg3_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["branch_id"] == 1


def test_create_branch_invalid_message(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]

    response = client.post(f"/api/chat/chats/{chat_id}/branch/99999")
    assert response.status_code == 404


def test_create_branch_chat_not_found(client):
    response = client.post("/api/chat/chats/99999/branch/1")
    assert response.status_code in [404, 500]


def test_get_branches(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]

    msg_id = _add_user_msg(client, chat_id, "Hello")
    client.post(f"/api/chat/chats/{chat_id}/branch/{msg_id}")

    response = client.get(f"/api/chat/chats/{chat_id}/branches")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["branches"]) >= 1


def test_get_branch_messages(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]

    msg_id = _add_user_msg(client, chat_id, "Hello")

    branch_resp = client.post(f"/api/chat/chats/{chat_id}/branch/{msg_id}")
    branch_id = branch_resp.json()["branch_id"]

    response = client.get(f"/api/chat/chats/{chat_id}/branches/{branch_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["messages"]) == 1


def test_switch_branch(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]

    msg_id = _add_user_msg(client, chat_id, "Hello")

    branch_resp = client.post(f"/api/chat/chats/{chat_id}/branch/{msg_id}")
    branch_id = branch_resp.json()["branch_id"]

    response = client.post(f"/api/chat/chats/{chat_id}/branches/{branch_id}/switch")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_get_branches_chat_not_found(client):
    response = client.get("/api/chat/chats/99999/branches")
    assert response.status_code == 404


def test_get_branch_messages_chat_not_found(client):
    response = client.get("/api/chat/chats/99999/branches/0")
    assert response.status_code == 404
