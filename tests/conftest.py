"""Shared test fixtures for AI Engine tests"""
import pytest
import os
import asyncio

os.environ.setdefault("CDN_CONFIG_URL", "")


@pytest.fixture(autouse=True)
def _stop_cleanup_task():
    """Ensure background cleanup task is stopped after each test"""
    yield
    try:
        from chat_module.router import stop_cleanup_task
        stop_cleanup_task()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _close_pending_tasks():
    """Cancel any pending asyncio tasks after each test to prevent teardown hangs"""
    yield
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
    except Exception:
        pass
