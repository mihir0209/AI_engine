"""Guardrails: one canonical tree for server, chat, and config."""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def test_server_shim_reexports_packaged_app():
    import importlib

    import server

    packaged_mod = importlib.import_module("ai_engine.server.app")
    assert server.app is packaged_mod.app


def test_chat_module_shims_match_canonical():
    from chat_module.db import ChatDB as shim_db
    from chat_module.router import router as shim_router
    from chat_module.websocket_manager import WebSocketManager as shim_ws
    from ai_engine.server.chat_module.db import ChatDB as canon_db
    from ai_engine.server.chat_module.router import router as canon_router
    from ai_engine.server.chat_module.websocket_manager import WebSocketManager as canon_ws

    assert shim_db is canon_db
    assert shim_router is canon_router
    assert shim_ws is canon_ws


def test_config_shim_is_core_config():
    import config
    import core.config as core_config

    assert config.AI_CONFIGS is core_config.AI_CONFIGS
    assert config.ENGINE_SETTINGS is core_config.ENGINE_SETTINGS


def test_no_duplicate_chat_implementations():
    """Root chat_module must be shims only (small files)."""
    for name in ("db.py", "router.py", "websocket_manager.py"):
        path = REPO / "chat_module" / name
        text = path.read_text(encoding="utf-8")
        assert "ai_engine.server.chat_module" in text, f"{name} must re-export canonical module"
        assert len(text.splitlines()) < 15, f"{name} must not duplicate implementation"


@pytest.mark.parametrize(
    "path",
    [
        REPO / "server.py",
        REPO / "config.py",
        REPO / "chat_module" / "router.py",
    ],
)
def test_legacy_entry_files_are_shims(path: Path):
    text = path.read_text(encoding="utf-8")
    assert len(text) < 800, f"{path.name} should be a thin shim, not a full copy"
