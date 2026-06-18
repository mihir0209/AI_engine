"""Tests for CLI tool"""
import pytest


def test_format_api_key_env_var():
    from cli import format_api_key
    result = format_api_key("MY_API_KEY")
    assert result == 'os.getenv("MY_API_KEY")'


def test_format_api_key_literal():
    from cli import format_api_key
    result = format_api_key("sk-12345")
    assert result == '"sk-12345"'


def test_format_api_key_already_formatted():
    from cli import format_api_key
    result = format_api_key('os.getenv("KEY")')
    assert result == 'os.getenv("KEY")'


def test_format_api_key_empty():
    from cli import format_api_key
    result = format_api_key("")
    assert result == "None"


def test_format_api_key_none():
    from cli import format_api_key
    result = format_api_key(None)
    assert result == "None"


def test_format_provider():
    from cli import format_provider
    config = {
        "id": 1, "priority": 1,
        "api_keys": ['os.getenv("TEST_KEY")'],
        "endpoint": "https://api.test.com/v1/chat/completions",
        "model_endpoint": "https://api.test.com/v1/models",
        "model_endpoint_auth": True,
        "model": "gpt-4",
        "format": "openai",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "rpm_limit": 30,
        "daily_limit": 500
    }
    result = format_provider("test_provider", config)
    assert '"test_provider":' in result
    assert '"id": 1' in result
    assert 'os.getenv("TEST_KEY")' in result


def test_format_provider_minimal():
    from cli import format_provider
    config = {
        "id": 1, "priority": 1,
        "api_keys": ["None"],
        "endpoint": "https://api.test.com/v1/chat/completions",
        "model": "gpt-4",
        "format": "openai"
    }
    result = format_provider("test", config)
    assert '"test":' in result
