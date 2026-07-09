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


def _reset_test_harness_state(engine) -> None:
    """Clear persisted key stats so mock-provider tests start from alpha."""
    if "test_harness" not in engine.providers:
        return

    engine.providers["test_harness"]["api_keys"] = [
        "test-key-alpha",
        "test-key-beta",
        "test-key-gamma",
    ]
    engine.provider_key_rotation["test_harness"] = 0
    engine.flagged_keys.pop("test_harness", None)
    engine.key_usage_stats["test_harness"] = {
        f"key_{i}": {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "last_used": None,
            "rate_limited": False,
            "weight": 1.0,
            "requests_this_minute": 0,
        }
        for i in range(3)
    }
    engine.key_request_count["test_harness"] = {f"key_{i}": [] for i in range(3)}
    engine.key_last_used["test_harness"] = {f"key_{i}": None for i in range(3)}


@pytest.fixture
def testing_engine(mock_provider_server):
    from core.ai_engine import AI_engine

    engine = AI_engine(verbose=False)
    assert "test_harness" in engine.providers
    _reset_test_harness_state(engine)
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