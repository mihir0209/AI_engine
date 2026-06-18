"""Tests for error codes and standardized error responses"""
import pytest


# === Error Code Tests ===

def test_error_code_values():
    from error_codes import ErrorCode
    assert ErrorCode.BAD_REQUEST.value == "BAD_REQUEST"
    assert ErrorCode.PROVIDER_NOT_FOUND.value == "PROVIDER_NOT_FOUND"
    assert ErrorCode.CIRCUIT_BREAKER_OPEN.value == "CIRCUIT_BREAKER_OPEN"


def test_error_response_to_dict():
    from error_codes import ErrorResponse, ErrorCode
    error = ErrorResponse(
        error="Test Error",
        code=ErrorCode.BAD_REQUEST,
        message="Something went wrong"
    )
    result = error.to_dict()
    assert result["error"] == "Test Error"
    assert result["code"] == "BAD_REQUEST"
    assert result["message"] == "Something went wrong"


def test_error_response_with_details():
    from error_codes import ErrorResponse, ErrorCode
    error = ErrorResponse(
        error="Test",
        code=ErrorCode.PROVIDER_ERROR,
        message="Failed",
        details={"provider": "openai"},
        suggestion="Try another provider"
    )
    result = error.to_dict()
    assert result["details"]["provider"] == "openai"
    assert result["suggestion"] == "Try another provider"


# === Error Factory Tests ===

def test_factory_provider_not_found():
    from error_codes import ErrorFactory
    error = ErrorFactory.provider_not_found("openai")
    assert error.code.value == "PROVIDER_NOT_FOUND"
    assert "openai" in error.message


def test_factory_model_not_found():
    from error_codes import ErrorFactory
    error = ErrorFactory.model_not_found("gpt-5")
    assert error.code.value == "MODEL_NOT_FOUND"
    assert "gpt-5" in error.message


def test_factory_no_providers():
    from error_codes import ErrorFactory
    error = ErrorFactory.no_providers()
    assert error.code.value == "NO_PROVIDERS_AVAILABLE"


def test_factory_provider_failed():
    from error_codes import ErrorFactory
    error = ErrorFactory.provider_failed("openai", "timeout")
    assert error.code.value == "PROVIDER_ERROR"
    assert "openai" in error.message
    assert "timeout" in error.message


def test_factory_chat_not_found():
    from error_codes import ErrorFactory
    error = ErrorFactory.chat_not_found(42)
    assert error.code.value == "CHAT_NOT_FOUND"
    assert "42" in error.message


def test_factory_rate_limited():
    from error_codes import ErrorFactory
    error = ErrorFactory.rate_limited(30)
    assert error.code.value == "RATE_LIMITED"
    assert error.details["retry_after"] == 30


def test_factory_unauthorized():
    from error_codes import ErrorFactory
    error = ErrorFactory.unauthorized()
    assert error.code.value == "UNAUTHORIZED"


def test_factory_forbidden():
    from error_codes import ErrorFactory
    error = ErrorFactory.forbidden("Admin only")
    assert error.code.value == "FORBIDDEN"
    assert "Admin only" in error.message


def test_factory_internal_error():
    from error_codes import ErrorFactory
    error = ErrorFactory.internal_error()
    assert error.code.value == "INTERNAL_ERROR"


def test_factory_circuit_breaker_open():
    from error_codes import ErrorFactory
    error = ErrorFactory.circuit_breaker_open("openai")
    assert error.code.value == "CIRCUIT_BREAKER_OPEN"
    assert "openai" in error.message


# === Status Code Tests ===

def test_get_http_status_code():
    from error_codes import get_http_status_code, ErrorCode
    assert get_http_status_code(ErrorCode.BAD_REQUEST) == 400
    assert get_http_status_code(ErrorCode.UNAUTHORIZED) == 401
    assert get_http_status_code(ErrorCode.NOT_FOUND) == 404
    assert get_http_status_code(ErrorCode.RATE_LIMITED) == 429
    assert get_http_status_code(ErrorCode.INTERNAL_ERROR) == 500
    assert get_http_status_code(ErrorCode.SERVICE_UNAVAILABLE) == 503
