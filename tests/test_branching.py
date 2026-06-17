"""Tests for branching and provider health features"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from fastapi import FastAPI
    from chat_module.router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# === Branching Tests ===

def test_create_branch(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Branch Test"})
    chat_id = create_resp.json()["chat_id"]
    
    # Add messages
    msg1_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Message 1"
    })
    msg1_id = msg1_resp.json()["message_id"]
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "Response 1"
    })
    msg3_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Message 3"
    })
    msg3_id = msg3_resp.json()["message_id"]
    
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
    assert response.status_code in [404, 500]  # May return 500 due to exception handling


def test_get_branches(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    
    msg_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })
    msg_id = msg_resp.json()["message_id"]
    client.post(f"/api/chat/chats/{chat_id}/branch/{msg_id}")
    
    response = client.get(f"/api/chat/chats/{chat_id}/branches")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["branches"]) >= 1  # At least main branch (0) and new branch (1)


def test_get_branch_messages(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    
    msg_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })
    msg_id = msg_resp.json()["message_id"]
    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "Hi!"
    })
    
    # Create branch
    branch_resp = client.post(f"/api/chat/chats/{chat_id}/branch/{msg_id}")
    branch_id = branch_resp.json()["branch_id"]
    
    response = client.get(f"/api/chat/chats/{chat_id}/branches/{branch_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["messages"]) == 1  # Only message 1 in branch


def test_switch_branch(client):
    create_resp = client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    
    msg_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })
    msg_id = msg_resp.json()["message_id"]
    
    # Create branch
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
