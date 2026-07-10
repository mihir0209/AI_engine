"""Fixtures for tests/features integration suite."""
import pytest

from tests.conftest import _reset_test_harness_state


@pytest.fixture
def reset_server_test_harness_keys():
    """Reset global server engine test_harness key state for mock-backed server tests."""
    from ai_engine.server.app import engine

    _reset_test_harness_state(engine)
    yield
