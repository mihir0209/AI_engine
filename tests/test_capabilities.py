"""Tests for capabilities and error messages"""
import pytest


# === Capability Manager Tests ===

def test_get_capabilities():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    caps = cm.get_capabilities("openai")
    assert caps is not None
    assert caps.vision is True
    assert caps.tool_calling is True


def test_get_unknown_provider():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    caps = cm.get_capabilities("unknown_provider")
    assert caps is None


def test_supports_vision():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    assert cm.supports_vision("openai") is True
    assert cm.supports_vision("anthropic") is True
    assert cm.supports_vision("groq") is False


def test_supports_tool_calling():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    assert cm.supports_tool_calling("openai") is True
    assert cm.supports_tool_calling("anthropic") is True


def test_get_providers_with_vision():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    providers = cm.get_providers_with_vision()
    assert "openai" in providers
    assert "anthropic" in providers
    assert "gemini" in providers


def test_get_fastest_providers():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    fastest = cm.get_fastest_providers(top_n=2)
    assert len(fastest) == 2


def test_get_cheapest_providers():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    cheapest = cm.get_cheapest_providers(top_n=2)
    assert len(cheapest) == 2


def test_get_provider_for_task():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    vision_providers = cm.get_provider_for_task("vision")
    assert "openai" in vision_providers
    
    fast_providers = cm.get_provider_for_task("fast")
    assert len(fast_providers) > 0


def test_get_all_capabilities():
    from capabilities import CapabilityManager
    cm = CapabilityManager()
    
    all_caps = cm.get_all_capabilities()
    assert "openai" in all_caps
    assert "vision" in all_caps["openai"]


def test_set_custom_capabilities():
    from capabilities import CapabilityManager, ProviderCapabilities
    cm = CapabilityManager()
    
    custom = ProviderCapabilities(provider="custom", vision=True, tool_calling=True)
    cm.set_capabilities("custom", custom)
    
    caps = cm.get_capabilities("custom")
    assert caps is not None
    assert caps.vision is True


# === Error Message Tests ===

def test_get_error_rate_limit():
    from capabilities import ErrorMessageManager
    error = ErrorMessageManager.get_error("rate_limit")
    
    assert error["code"] == "RATE_LIMIT_EXCEEDED"
    assert "rate limit" in error["message"].lower()


def test_get_error_auth():
    from capabilities import ErrorMessageManager
    error = ErrorMessageManager.get_error("auth_error")
    
    assert error["code"] == "AUTH_FAILED"


def test_get_error_with_details():
    from capabilities import ErrorMessageManager
    error = ErrorMessageManager.get_error("timeout", "Connection timed out after 30s")
    
    assert "details" in error
    assert "Connection timed out" in error["details"]


def test_get_unknown_error():
    from capabilities import ErrorMessageManager
    error = ErrorMessageManager.get_error("some_unknown_error")
    
    assert error["code"] == "UNKNOWN_ERROR"


def test_get_all_errors():
    from capabilities import ErrorMessageManager
    errors = ErrorMessageManager.get_all_errors()
    
    assert len(errors) > 0
    assert "rate_limit" in errors
    assert "auth_error" in errors
