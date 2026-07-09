"""Tests for capabilities and error messages"""


# === Capability Manager Tests ===

def test_get_provider_capabilities():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    caps = cm.get_provider_capabilities("gemini")
    assert caps is not None
    assert caps.vision is True
    assert caps.tool_calling is True


def test_get_unknown_provider():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    caps = cm.get_provider_capabilities("unknown_provider")
    assert caps is None


def test_supports_vision():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    assert cm.supports_vision("gemini") is True
    assert cm.supports_vision("openrouter") is True
    assert cm.supports_vision("groq") is False


def test_supports_vision_with_model():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    assert cm.supports_vision("groq", "meta-llama/llama-4-scout-17b-16e-instruct") is False
    assert cm.supports_vision("groq", "llama-3.3-70b-versatile") is False


def test_supports_tool_calling():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    assert cm.supports_tool_calling("gemini") is True
    assert cm.supports_tool_calling("groq") is True


def test_get_vision_providers():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    providers = cm.get_vision_providers()
    assert isinstance(providers, list)
    assert len(providers) >= 1
    # Self-hosted vision provider is always configured (no API key required)
    assert "g4f_gemini" in providers
    for name in providers:
        assert cm.supports_vision(name)


def test_get_max_context():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    ctx = cm.get_max_context("gemini", "gemini-2.5-flash")
    assert ctx == 1000000


def test_check_image_compatibility():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    result = cm.check_image_compatibility("gemini", "gemini-2.5-flash")
    assert result["compatible"] is True

    result = cm.check_image_compatibility("groq", "llama-3.3-70b-versatile")
    assert result["compatible"] is False
    assert len(result["suggestions"]) > 0


def test_get_all_capabilities():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    all_caps = cm.get_all_capabilities()
    assert "gemini" in all_caps
    assert "vision" in all_caps["gemini"]


def test_get_model_list():
    from core.capabilities import CapabilityManager
    cm = CapabilityManager()

    models = cm.get_model_list()
    assert len(models) > 0
    gemini_models = [m for m in models if m["provider"] == "gemini"]
    assert len(gemini_models) > 0
    assert any(m["vision"] for m in gemini_models)


# === Error Message Tests ===

def test_get_error_rate_limit():
    from core.capabilities import ErrorMessageManager
    error = ErrorMessageManager.get_error("rate_limit")

    assert error["code"] == "RATE_LIMIT_EXCEEDED"
    assert "rate limit" in error["message"].lower()


def test_get_error_auth():
    from core.capabilities import ErrorMessageManager
    error = ErrorMessageManager.get_error("auth_error")

    assert error["code"] == "AUTH_FAILED"


def test_get_error_with_details():
    from core.capabilities import ErrorMessageManager
    error = ErrorMessageManager.get_error("timeout", "Connection timed out after 30s")

    assert "details" in error
    assert "Connection timed out" in error["details"]


def test_get_unknown_error():
    from core.capabilities import ErrorMessageManager
    error = ErrorMessageManager.get_error("some_unknown_error")

    assert error["code"] == "UNKNOWN_ERROR"


def test_get_all_errors():
    from core.capabilities import ErrorMessageManager
    errors = ErrorMessageManager.get_all_errors()

    assert len(errors) > 0
    assert "rate_limit" in errors
    assert "auth_error" in errors
