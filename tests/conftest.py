"""Shared test fixtures for AI Engine tests"""
import sys
import os
import pytest

# Add project root to sys.path so 'from core.X import' works in CI
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
