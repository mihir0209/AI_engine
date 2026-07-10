"""Tests for new chat features: edit, regenerate, search, export"""


# === Message Editing Tests ===

def test_edit_message(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    msg_resp = server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Original content"
    })
    message_id = msg_resp.json()["message_id"]

    response = server_client.put(f"/api/chat/messages/{message_id}", json={
        "content": "Edited content"
    })
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["message"]["content"] == "Edited content"


def test_edit_message_not_found(server_client):
    response = server_client.put("/api/chat/messages/99999", json={
        "content": "New content"
    })
    assert response.status_code == 404


def test_edit_message_empty_content(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    msg_resp = server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Original"
    })
    message_id = msg_resp.json()["message_id"]

    response = server_client.put(f"/api/chat/messages/{message_id}", json={
        "content": ""
    })
    assert response.status_code == 422


# === Regenerate Tests ===

def test_regenerate_response(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    msg_resp = server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })
    message_id = msg_resp.json()["message_id"]

    response = server_client.post(f"/api/chat/chats/{chat_id}/regenerate/{message_id}")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_regenerate_from_assistant_message(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    msg_resp = server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "System prompt"
    })
    message_id = msg_resp.json()["message_id"]

    response = server_client.post(f"/api/chat/chats/{chat_id}/regenerate/{message_id}")
    assert response.status_code == 400


def test_regenerate_chat_not_found(server_client):
    response = server_client.post("/api/chat/chats/99999/regenerate/1")
    assert response.status_code == 404


# === Search Tests ===

def test_search_messages(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello world"
    })
    server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Goodbye world"
    })
    server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Something else"
    })

    response = server_client.post("/api/chat/search", json={
        "query": "world"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] >= 2


def test_search_messages_specific_chat(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test"})
    chat_id = create_resp.json()["chat_id"]
    server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "unique_term"
    })

    response = server_client.post("/api/chat/search", json={
        "query": "unique_term",
        "chat_id": chat_id
    })
    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_search_no_results(server_client):
    response = server_client.post("/api/chat/search", json={
        "query": "nonexistent_term_xyz"
    })
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_search_empty_query(server_client):
    response = server_client.post("/api/chat/search", json={
        "query": ""
    })
    assert response.status_code == 422


# === Export Tests ===

def test_export_markdown(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test Chat"})
    chat_id = create_resp.json()["chat_id"]
    server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })
    server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "Hi there!"
    })

    response = server_client.get(f"/api/chat/chats/{chat_id}/export?format=markdown")
    assert response.status_code == 200
    data = response.json()
    assert "export" in data
    assert "Test Chat" in data["export"]
    assert "Hello" in data["export"]


def test_export_json(server_client):
    create_resp = server_client.post("/api/chat/chats", json={"title": "Test Chat"})
    chat_id = create_resp.json()["chat_id"]
    server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello"
    })

    response = server_client.get(f"/api/chat/chats/{chat_id}/export?format=json")
    assert response.status_code == 200
    data = response.json()
    assert "chat" in data
    assert "messages" in data
    assert data["chat"]["title"] == "Test Chat"


def test_export_chat_not_found(server_client):
    response = server_client.get("/api/chat/chats/99999/export")
    assert response.status_code == 404
