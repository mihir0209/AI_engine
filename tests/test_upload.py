"""Tests for file upload functionality"""
import pytest
from io import BytesIO

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from fastapi import FastAPI
    from chat_module.router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# === File Upload Tests ===

def test_upload_text_file(client):
    content = b"Hello, this is a test file content"
    response = client.post(
        "/api/chat/upload",
        files={"file": ("test.txt", BytesIO(content), "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["filename"] == "test.txt"
    assert data["type"] == "document"
    assert data["size"] == len(content)


def test_upload_python_file(client):
    content = b"print('hello world')"
    response = client.post(
        "/api/chat/upload",
        files={"file": ("test.py", BytesIO(content), "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["extension"] == ".py"


def test_upload_with_chat_id(client):
    # Create chat first
    create_resp = client.post("/api/chat/chats", json={"title": "Upload Test"})
    chat_id = create_resp.json()["chat_id"]

    content = b"File content for chat"
    response = client.post(
        f"/api/chat/upload?chat_id={chat_id}",
        files={"file": ("document.txt", BytesIO(content), "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "message_id" in data


def test_upload_invalid_file_type(client):
    content = b"test"
    response = client.post(
        "/api/chat/upload",
        files={"file": ("malware.exe", BytesIO(content), "application/octet-stream")}
    )
    assert response.status_code == 400


def test_upload_too_large(client):
    # Create large content (11MB)
    content = b"x" * (11 * 1024 * 1024)
    response = client.post(
        "/api/chat/upload",
        files={"file": ("large.txt", BytesIO(content), "text/plain")}
    )
    assert response.status_code == 413


def test_get_upload_info(client):
    # Upload a file first
    content = b"Test content"
    upload_resp = client.post(
        "/api/chat/upload",
        files={"file": ("info_test.txt", BytesIO(content), "text/plain")}
    )
    saved_as = upload_resp.json()["saved_as"]

    # Get file info
    response = client.get(f"/api/chat/uploads/{saved_as}")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == saved_as
    assert data["type"] == "document"


def test_get_upload_not_found(client):
    response = client.get("/api/chat/uploads/nonexistent.txt")
    assert response.status_code == 404


def test_upload_markdown_file(client):
    content = b"# Hello World\n\nThis is markdown"
    response = client.post(
        "/api/chat/upload",
        files={"file": ("readme.md", BytesIO(content), "text/markdown")}
    )
    assert response.status_code == 200
    assert response.json()["extension"] == ".md"


def test_upload_json_file(client):
    content = b'{"key": "value"}'
    response = client.post(
        "/api/chat/upload",
        files={"file": ("data.json", BytesIO(content), "application/json")}
    )
    assert response.status_code == 200
    assert response.json()["extension"] == ".json"
