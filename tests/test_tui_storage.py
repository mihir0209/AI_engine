"""Tests for TUI chat persistence."""
import json
import os
from pathlib import Path

import pytest

from ai_engine.tui_storage import (
    ChatStorage,
    _normalize_cwd,
    export_chat_json,
    export_chat_markdown,
    write_chat_export,
)


@pytest.fixture
def storage(tmp_path):
    return ChatStorage(root=tmp_path / "chatdata")


def test_load_empty_returns_none(storage):
    assert storage.load() is None


def test_save_and_load_roundtrip(storage):
    chats = {
        1: {"title": "Hello", "messages": [{"role": "user", "content": "Hi"}]},
        2: {"title": "Other", "messages": []},
    }
    storage.save_session(
        chats=chats,
        chat_counter=2,
        current_chat_id=1,
        chat_order=[1, 2],
        last_cwd="/tmp/project",
        current_model="gpt-4o",
        current_provider="groq",
    )
    loaded = storage.load()
    assert loaded is not None
    assert loaded["chat_counter"] == 2
    assert loaded["current_chat_id"] == 1
    assert loaded["last_cwd"] == "/tmp/project"
    assert loaded["current_model"] == "gpt-4o"
    assert loaded["current_provider"] == "groq"
    assert loaded["chats"][1]["title"] == "Hello"
    assert len(loaded["chats"][1]["messages"]) == 1


def test_last_cwd_single_value_overwrites(storage):
    storage.save_last_cwd("/first/path")
    storage.save_last_cwd("/second/path")
    loaded = storage.load() or {}
    with open(storage.meta_file, encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["last_cwd"] == "/second/path"


def test_normalize_cwd_file_becomes_parent(tmp_path):
    f = tmp_path / "img.png"
    f.write_text("x")
    assert _normalize_cwd(str(f)) == str(tmp_path)


def test_system_prompt_persisted(storage):
    chats = {
        1: {
            "title": "Prompted",
            "messages": [{"role": "user", "content": "Hi"}],
            "system_prompt": "You are concise.",
        },
    }
    storage.save_session(
        chats=chats,
        chat_counter=1,
        current_chat_id=1,
        chat_order=[1],
        last_cwd=os.getcwd(),
    )
    loaded = storage.load()
    assert loaded["chats"][1]["system_prompt"] == "You are concise."


def test_export_markdown_and_json(tmp_path):
    chat = {
        "title": "Export Me!",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ],
        "system_prompt": "Be brief.",
        "created_at": 1.0,
        "updated_at": 2.0,
    }
    md = export_chat_markdown(chat, model="gpt-4o", provider="groq")
    assert "# Export Me!" in md
    assert "Hello" in md
    assert "Be brief." in md
    assert "groq" in md

    payload = export_chat_json(chat, chat_id=7, model="gpt-4o", provider="groq")
    assert payload["chat"]["id"] == 7
    assert payload["chat"]["system_prompt"] == "Be brief."
    assert len(payload["messages"]) == 2

    out = tmp_path / "exports"
    written = write_chat_export(
        chat, chat_id=7, path=str(out), fmt="markdown", model="gpt-4o", provider="groq"
    )
    assert written.endswith(".md")
    assert "Export Me" in Path(written).read_text(encoding="utf-8")


def test_chat_favorite_and_intent_roundtrip(storage):
    storage.save_session(
        chats={1: {"title": "A", "messages": [], "favorite": True}},
        chat_counter=1,
        current_chat_id=1,
        chat_order=[1],
        last_cwd=os.getcwd(),
        intent_routing_enabled=False,
    )
    loaded = storage.load()
    assert loaded is not None
    assert loaded["chats"][1]["favorite"] is True
    assert loaded["intent_routing_enabled"] is False


def test_legacy_favorite_models_migrated_from_meta(storage):
    meta = {
        "version": 2,
        "chat_counter": 1,
        "current_chat_id": 1,
        "chat_order": [1],
        "last_cwd": os.getcwd(),
        "favorite_models": ["gpt-4o|groq", "claude-3|openrouter"],
        "intent_routing_enabled": True,
    }
    storage.meta_file.parent.mkdir(parents=True, exist_ok=True)
    with open(storage.meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    (storage.chats_dir).mkdir(parents=True, exist_ok=True)
    (storage.chats_dir / "1.json").write_text(
        json.dumps({"id": 1, "title": "A", "messages": [], "favorite": False}),
        encoding="utf-8",
    )
    loaded = storage.load()
    assert loaded is not None
    assert loaded["_legacy_favorite_models"] == [
        "gpt-4o|groq",
        "claude-3|openrouter",
    ]


def test_stale_chat_files_removed(storage):
    storage.save_session(
        chats={1: {"title": "A", "messages": []}},
        chat_counter=1,
        current_chat_id=1,
        chat_order=[1],
        last_cwd=os.getcwd(),
    )
    stale = storage.chats_dir / "99.json"
    stale.write_text(json.dumps({"id": 99, "title": "old", "messages": []}))
    storage.save_session(
        chats={1: {"title": "A", "messages": []}},
        chat_counter=1,
        current_chat_id=1,
        chat_order=[1],
        last_cwd=os.getcwd(),
    )
    assert not stale.exists()