"""Tests for chat_module/websocket_manager.py"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from chat_module.websocket_manager import WebSocketManager


@pytest.fixture
def ws_manager():
    return WebSocketManager()


# === Connection Management ===

def test_init(ws_manager):
    assert ws_manager.active_connections == {}


@pytest.mark.asyncio
async def test_connect(ws_manager):
    websocket = AsyncMock()
    await ws_manager.connect(websocket, chat_id=1)
    assert 1 in ws_manager.active_connections
    assert websocket in ws_manager.active_connections[1]


@pytest.mark.asyncio
async def test_connect_multiple_clients(ws_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await ws_manager.connect(ws1, chat_id=1)
    await ws_manager.connect(ws2, chat_id=1)
    assert len(ws_manager.active_connections[1]) == 2


@pytest.mark.asyncio
async def test_connect_different_chats(ws_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await ws_manager.connect(ws1, chat_id=1)
    await ws_manager.connect(ws2, chat_id=2)
    assert 1 in ws_manager.active_connections
    assert 2 in ws_manager.active_connections


def test_disconnect(ws_manager):
    websocket = MagicMock()
    ws_manager.active_connections = {1: [websocket]}
    ws_manager.disconnect(websocket, chat_id=1)
    assert 1 not in ws_manager.active_connections


def test_disconnect_removes_empty_chat(ws_manager):
    websocket = MagicMock()
    ws_manager.active_connections = {1: [websocket]}
    ws_manager.disconnect(websocket, chat_id=1)
    assert 1 not in ws_manager.active_connections


def test_disconnect_not_in_list(ws_manager):
    ws1 = MagicMock()
    ws2 = MagicMock()
    ws_manager.active_connections = {1: [ws1]}
    # Should not raise
    ws_manager.disconnect(ws2, chat_id=1)


def test_disconnect_nonexistent_chat(ws_manager):
    ws = MagicMock()
    # Should not raise
    ws_manager.disconnect(ws, chat_id=999)


# === Message Sending ===

@pytest.mark.asyncio
async def test_send_personal_message(ws_manager):
    websocket = AsyncMock()
    await ws_manager.send_personal_message("hello", websocket)
    websocket.send_text.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_send_personal_message_error(ws_manager):
    websocket = AsyncMock()
    websocket.send_text.side_effect = Exception("connection closed")
    # Should not raise
    await ws_manager.send_personal_message("hello", websocket)


@pytest.mark.asyncio
async def test_broadcast_to_chat(ws_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws_manager.active_connections = {1: [ws1, ws2]}

    await ws_manager.broadcast_to_chat("hello", chat_id=1)
    ws1.send_text.assert_called_once_with("hello")
    ws2.send_text.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_broadcast_to_chat_with_disconnected(ws_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws2.send_text.side_effect = Exception("disconnected")
    ws_manager.active_connections = {1: [ws1, ws2]}

    await ws_manager.broadcast_to_chat("hello", chat_id=1)
    # ws1 should still be connected, ws2 should be removed
    assert ws1 in ws_manager.active_connections[1]
    assert ws2 not in ws_manager.active_connections[1]


@pytest.mark.asyncio
async def test_broadcast_to_chat_no_connections(ws_manager):
    # Should not raise
    await ws_manager.broadcast_to_chat("hello", chat_id=999)


@pytest.mark.asyncio
async def test_send_typing_indicator(ws_manager):
    ws = AsyncMock()
    ws_manager.active_connections = {1: [ws]}
    await ws_manager.send_typing_indicator(1, is_typing=True)
    ws.send_text.assert_called_once()
    sent_data = json.loads(ws.send_text.call_args[0][0])
    assert sent_data["type"] == "typing_indicator"
    assert sent_data["is_typing"] is True


@pytest.mark.asyncio
async def test_broadcast_to_all(ws_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws_manager.active_connections = {1: [ws1], 2: [ws2]}

    await ws_manager.broadcast_to_all("hello all")
    ws1.send_text.assert_called_once_with("hello all")
    ws2.send_text.assert_called_once_with("hello all")


@pytest.mark.asyncio
async def test_broadcast_to_all_with_errors(ws_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws1.send_text.side_effect = Exception("error")
    ws_manager.active_connections = {1: [ws1], 2: [ws2]}

    await ws_manager.broadcast_to_all("hello")
    # ws1 should be removed, ws2 should still work
    assert 1 not in ws_manager.active_connections
    assert 2 in ws_manager.active_connections


# === Notification Tests ===

@pytest.mark.asyncio
async def test_notify_chat_deleted(ws_manager):
    ws = AsyncMock()
    ws_manager.active_connections = {1: [ws]}

    await ws_manager.notify_chat_deleted(1)
    ws.send_text.assert_called_once()
    ws.close.assert_called_once()
    assert 1 not in ws_manager.active_connections


@pytest.mark.asyncio
async def test_notify_chat_deleted_broadcasts_to_others(ws_manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws_manager.active_connections = {1: [ws1], 2: [ws2]}

    await ws_manager.notify_chat_deleted(1)
    # ws2 should receive the deletion notification
    assert ws2.send_text.called


# === Stats Methods ===

def test_get_connection_count(ws_manager):
    ws_manager.active_connections = {1: [MagicMock(), MagicMock()]}
    assert ws_manager.get_connection_count(1) == 2
    assert ws_manager.get_connection_count(999) == 0


def test_get_total_connections(ws_manager):
    ws_manager.active_connections = {
        1: [MagicMock(), MagicMock()],
        2: [MagicMock()]
    }
    assert ws_manager.get_total_connections() == 3


def test_get_active_chats(ws_manager):
    ws_manager.active_connections = {1: [MagicMock()], 3: [MagicMock()]}
    active = ws_manager.get_active_chats()
    assert sorted(active) == [1, 3]
