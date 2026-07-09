"""Tests for branching and provider health features"""


# === Branching Tests ===

def _add_user_msg(server_client, chat_id, content):
    """Add a user message that won't trigger AI processing (by also adding system response)"""
    resp = server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": content
    })
    msg_id = resp.json()["message_id"]
    # Add system response to prevent background AI processing from blocking
    server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": f"Response to: {content}"
    })
    return msg_id


def test_create_branch(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Branch Test"})
    chat_id = create_resp.json()["chat_id"]

    msg1_id = _add_user_msg(server_client, chat_id, "Message 1")
    msg3_id = _add_user_msg(server_client, chat_id, "Message 3")

    # Create branch from message 3
    response = server_client.post(f"/api/chat/chats/{chat_id}/branch/{msg3_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["branch_id"] == 1


def test_create_branch_invalid_message(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]

    response = server_client.post(f"/api/chat/chats/{chat_id}/branch/99999")
    assert response.status_code == 404


def test_create_branch_chat_not_found(server_client):
    response = server_client.post("/api/chat/chats/99999/branch/1")
    assert response.status_code in [404, 500]


def test_get_branches(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]

    msg_id = _add_user_msg(server_client, chat_id, "Hello")
    server_client.post(f"/api/chat/chats/{chat_id}/branch/{msg_id}")

    response = server_client.get(f"/api/chat/chats/{chat_id}/branches")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["branches"]) >= 1


def test_get_branch_messages(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]

    msg_id = _add_user_msg(server_client, chat_id, "Hello")

    branch_resp = server_client.post(f"/api/chat/chats/{chat_id}/branch/{msg_id}")
    branch_id = branch_resp.json()["branch_id"]

    response = server_client.get(f"/api/chat/chats/{chat_id}/branches/{branch_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["messages"]) == 1


def test_switch_branch(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]

    msg_id = _add_user_msg(server_client, chat_id, "Hello")

    branch_resp = server_client.post(f"/api/chat/chats/{chat_id}/branch/{msg_id}")
    branch_id = branch_resp.json()["branch_id"]

    response = server_client.post(f"/api/chat/chats/{chat_id}/branches/{branch_id}/switch")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_get_branches_chat_not_found(server_client):
    response = server_client.get("/api/chat/chats/99999/branches")
    assert response.status_code == 404


def test_get_branch_messages_chat_not_found(server_client):
    response = server_client.get("/api/chat/chats/99999/branches/0")
    assert response.status_code == 404
