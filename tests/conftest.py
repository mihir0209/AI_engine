"""Pytest configuration for AI Synapse tests."""
try:
    import pytest_asyncio  # noqa: F401
except ImportError:
    pass
else:
    pytest_plugins = ("pytest_asyncio",)