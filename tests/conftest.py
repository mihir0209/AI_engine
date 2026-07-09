"""Pytest configuration for AI Synapse tests."""
import os

import pytest

# Default: never hit live providers in tests
os.environ.setdefault("AI_ENGINE_MODE", "testing")

try:
    import pytest_asyncio  # noqa: F401
except ImportError:
    pass
else:
    pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def mock_provider_server():
    from tests.server import MOCK_PROVIDER_BASE, start, stop, wait_ready

    proc = start()
    wait_ready()
    yield MOCK_PROVIDER_BASE
    stop(proc)


@pytest.fixture
def testing_engine(mock_provider_server):
    from core.ai_engine import AI_engine

    engine = AI_engine(verbose=False)
    assert "test_harness" in engine.providers
    return engine


@pytest.fixture(scope="session")
def server_client():
    from fastapi.testclient import TestClient

    from ai_engine.server.app import app

    return TestClient(app)


def pytest_collection_modifyitems(config, items):
    if os.getenv("AI_ENGINE_RUN_LIVE_TESTS"):
        return
    skip_live = pytest.mark.skip(reason="live provider test — set AI_ENGINE_RUN_LIVE_TESTS=1")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)