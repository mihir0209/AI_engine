"""Textual Pilot integration tests for ChatTUI."""
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from ai_engine.tui import ChatTUI
from ai_engine.tui.common import is_image_path
from ai_engine.tui.preferences import PreferencesStore
from ai_engine.tui.storage import ChatStorage


@pytest.fixture
def isolated_tui_storage(tmp_path: Path):
    """Never touch ~/.ai-engine/chatdata during tests."""
    root = tmp_path / "chatdata"
    storage = ChatStorage(root=root)
    prefs = PreferencesStore(path=tmp_path / "preferences.json")
    return storage, prefs


async def _run_mount_test(storage: ChatStorage, prefs: PreferencesStore):
    app = ChatTUI(storage=storage, preferences=prefs)
    async with app.run_test() as pilot:
        composer = app.query_one("ComposerInput")
        assert composer is not None
        await pilot.pause()


async def _run_new_chat_test(storage: ChatStorage, prefs: PreferencesStore):
    app = ChatTUI(storage=storage, preferences=prefs)
    app.chats = {
        1: {
            "title": "One",
            "messages": [{"role": "user", "content": "Hi"}],
            "created_at": 1.0,
            "updated_at": 1.0,
        },
    }
    app.current_chat_id = 1
    app.chat_counter = 1
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert app.current_chat_id != 1 or len(app.chats) > 1


def test_switch_blocked_while_processing(isolated_tui_storage):
    storage, prefs = isolated_tui_storage
    app = ChatTUI(storage=storage, preferences=prefs)
    app.chats = {
        1: {"title": "A", "messages": [], "created_at": 1.0, "updated_at": 1.0},
        2: {"title": "B", "messages": [], "created_at": 2.0, "updated_at": 2.0},
    }
    app.current_chat_id = 1
    app.is_processing = True
    app._switch_to_chat(2)
    assert app.current_chat_id == 1


async def _run_slash_suggest_test(storage: ChatStorage, prefs: PreferencesStore):
    app = ChatTUI(storage=storage, preferences=prefs)
    async with app.run_test() as pilot:
        await pilot.click("#user-input")
        await pilot.press("/", "h", "e", "l")
        await pilot.pause()
        suggest = app.query_one("#slash-suggest")
        assert suggest.has_class("-visible")


def test_app_mounts_with_composer(isolated_tui_storage):
    storage, prefs = isolated_tui_storage
    asyncio.run(_run_mount_test(storage, prefs))


def test_new_chat_action(isolated_tui_storage):
    storage, prefs = isolated_tui_storage
    asyncio.run(_run_new_chat_test(storage, prefs))


def test_slash_suggest_visible_on_slash(isolated_tui_storage):
    storage, prefs = isolated_tui_storage
    asyncio.run(_run_slash_suggest_test(storage, prefs))


def test_is_image_path_helper():
    assert is_image_path("/tmp/photo.PNG")
    assert not is_image_path("/tmp/readme.md")