"""Shared test fixtures for AI Engine tests"""
import pytest
import os

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
