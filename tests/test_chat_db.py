"""Tests for chat_module/db.py"""
import os
import pytest

from chat_module.db import ChatDB


@pytest.fixture
def chat_db(tmp_path):
    db_path = str(tmp_path / "test_chat.db")
    return ChatDB(db_path=db_path)


# === Database Initialization ===

def test_db_init(chat_db):
    assert os.path.exists(chat_db.db_path)


def test_db_tables_exist(chat_db):
    import sqlite3
    with sqlite3.connect(chat_db.db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "chats" in table_names
        assert "messages" in table_names


# === Chat Operations ===

def test_create_chat(chat_db):
    chat_id = chat_db.create_chat(
        title="Test Chat",
        model="gpt-4",
        provider="openai"
    )
    assert chat_id > 0


def test_get_chat(chat_db):
    chat_id = chat_db.create_chat(title="Test Chat")
    chat = chat_db.get_chat(chat_id)
    assert chat is not None
    assert chat["title"] == "Test Chat"
    assert chat["model"] is None


def test_get_chat_not_found(chat_db):
    chat = chat_db.get_chat(99999)
    assert chat is None


def test_get_chats(chat_db):
    chat_db.create_chat(title="Chat 1")
    chat_db.create_chat(title="Chat 2")
    chats = chat_db.get_chats()
    assert len(chats) == 2


def test_get_chats_with_limit(chat_db):
    for i in range(10):
        chat_db.create_chat(title=f"Chat {i}")
    chats = chat_db.get_chats(limit=5)
    assert len(chats) == 5


def test_get_chats_exclude_temporary(chat_db):
    chat_db.create_chat(title="Permanent", is_temporary=False)
    chat_db.create_chat(title="Temporary", is_temporary=True)
    chats = chat_db.get_chats(include_temporary=False)
    assert len(chats) == 1
    assert chats[0]["title"] == "Permanent"


def test_get_chats_include_temporary(chat_db):
    chat_db.create_chat(title="Permanent", is_temporary=False)
    chat_db.create_chat(title="Temporary", is_temporary=True)
    chats = chat_db.get_chats(include_temporary=True)
    assert len(chats) == 2


def test_delete_chat(chat_db):
    chat_id = chat_db.create_chat(title="To Delete")
    assert chat_db.delete_chat(chat_id) is True
    assert chat_db.get_chat(chat_id) is None


def test_delete_chat_not_found(chat_db):
    assert chat_db.delete_chat(99999) is False


def test_update_chat(chat_db):
    chat_id = chat_db.create_chat(title="Original")
    success = chat_db.update_chat(chat_id, title="Updated")
    assert success is True
    chat = chat_db.get_chat(chat_id)
    assert chat["title"] == "Updated"


def test_update_chat_no_fields(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    assert chat_db.update_chat(chat_id) is False


def test_update_chat_invalid_fields(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    assert chat_db.update_chat(chat_id, invalid_field="value") is False


# === Message Operations ===

def test_add_message(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    msg_id = chat_db.add_message(
        chat_id=chat_id,
        role="user",
        content="Hello"
    )
    assert msg_id > 0


def test_add_message_chat_not_found(chat_db):
    with pytest.raises(ValueError, match="does not exist"):
        chat_db.add_message(chat_id=99999, role="user", content="Hi")


def test_get_messages(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    chat_db.add_message(chat_id=chat_id, role="user", content="Hello")
    chat_db.add_message(chat_id=chat_id, role="assistant", content="Hi")
    messages = chat_db.get_messages(chat_id)
    assert len(messages) == 2


def test_get_messages_with_limit(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    for i in range(10):
        chat_db.add_message(chat_id=chat_id, role="user", content=f"Msg {i}")
    messages = chat_db.get_messages(chat_id, limit=5)
    assert len(messages) == 5


def test_get_messages_after_id(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    id1 = chat_db.add_message(chat_id=chat_id, role="user", content="Msg 1")
    chat_db.add_message(chat_id=chat_id, role="user", content="Msg 2")
    messages = chat_db.get_messages(chat_id, after_id=id1)
    assert len(messages) == 1


def test_get_context_messages(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    chat_db.add_message(chat_id=chat_id, role="user", content="Hello", tokens=10)
    chat_db.add_message(chat_id=chat_id, role="assistant", content="Hi", tokens=10)
    context = chat_db.get_context_messages(chat_id, max_tokens=100)
    assert len(context) == 2


def test_get_context_messages_token_limit(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    for i in range(20):
        chat_db.add_message(chat_id=chat_id, role="user", content=f"Msg {i}", tokens=100)
    context = chat_db.get_context_messages(chat_id, max_tokens=500)
    assert len(context) < 20


def test_message_with_metadata(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    metadata = {"provider": "openai", "model": "gpt-4"}
    chat_db.add_message(
        chat_id=chat_id,
        role="user",
        content="Hello",
        metadata=metadata
    )
    messages = chat_db.get_messages(chat_id)
    assert messages[0]["metadata"]["provider"] == "openai"


def test_message_with_response_to(chat_db):
    chat_id = chat_db.create_chat(title="Test")
    user_msg_id = chat_db.add_message(chat_id=chat_id, role="user", content="Hello")
    chat_db.add_message(
        chat_id=chat_id,
        role="assistant",
        content="Hi",
        response_to=user_msg_id
    )
    messages = chat_db.get_messages(chat_id)
    assistant_msg = [m for m in messages if m["role"] == "assistant"][0]
    assert assistant_msg["response_to"] == user_msg_id


# === Temporary Chat Operations ===

def test_create_temporary_chat(chat_db):
    chat_id = chat_db.create_chat(
        title="Temp Chat",
        is_temporary=True,
        temporary_timer_minutes=10
    )
    chat = chat_db.get_chat(chat_id)
    assert chat["is_temporary"] == 1
    assert chat["temporary_timer_minutes"] == 10


def test_convert_to_permanent(chat_db):
    chat_id = chat_db.create_chat(title="Temp", is_temporary=True)
    assert chat_db.convert_chat_to_permanent(chat_id) is True
    chat = chat_db.get_chat(chat_id)
    assert chat["is_temporary"] == 0


def test_convert_to_permanent_with_title(chat_db):
    chat_id = chat_db.create_chat(title="Temp", is_temporary=True)
    chat_db.convert_chat_to_permanent(chat_id, new_title="New Title")
    chat = chat_db.get_chat(chat_id)
    assert chat["title"] == "New Title"


def test_convert_already_permanent(chat_db):
    chat_id = chat_db.create_chat(title="Permanent", is_temporary=False)
    assert chat_db.convert_chat_to_permanent(chat_id) is False


def test_convert_nonexistent(chat_db):
    assert chat_db.convert_chat_to_permanent(99999) is False


def test_get_expired_temporary_chats(chat_db):
    import sqlite3
    chat_id = chat_db.create_chat(title="Old Temp", is_temporary=True, temporary_timer_minutes=5)
    # Manually set created_at to 10 minutes ago
    with sqlite3.connect(chat_db.db_path) as conn:
        conn.execute(
            "UPDATE chats SET created_at = datetime('now', '-10 minutes') WHERE id = ?",
            (chat_id,)
        )
        conn.commit()
    expired = chat_db.get_expired_temporary_chats()
    assert len(expired) == 1


def test_cleanup_temporary_chats(chat_db):
    import sqlite3
    chat_id = chat_db.create_chat(title="Old Temp", is_temporary=True)
    with sqlite3.connect(chat_db.db_path) as conn:
        conn.execute(
            "UPDATE chats SET created_at = datetime('now', '-25 hours') WHERE id = ?",
            (chat_id,)
        )
        conn.commit()
    deleted = chat_db.cleanup_temporary_chats(max_age_hours=24)
    assert deleted == 1
    assert chat_db.get_chat(chat_id) is None


# === Statistics ===

def test_get_chat_stats(chat_db):
    chat_db.create_chat(title="C1")
    chat_db.create_chat(title="C2", is_temporary=True)
    chat_id = chat_db.create_chat(title="C3")
    chat_db.add_message(chat_id=chat_id, role="user", content="Hi")
    chat_db.add_message(chat_id=chat_id, role="assistant", content="Hello")

    stats = chat_db.get_chat_stats()
    assert stats["total_chats"] == 3
    assert stats["permanent_chats"] == 2
    assert stats["temporary_chats"] == 1
    assert stats["total_messages"] == 2
    assert stats["user_messages"] == 1
    assert stats["assistant_messages"] == 1


# === Connection ===

def test_get_connection(chat_db):
    conn = chat_db.get_connection()
    assert conn is not None
    conn.close()
