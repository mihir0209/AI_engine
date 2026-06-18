"""
Error codes and standardized error responses for AI Engine
"""
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class ErrorCode(Enum):
    """Standard error codes"""
    # Client errors (4xx)
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNPROCESSABLE = "UNPROCESSABLE"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    GATEWAY_TIMEOUT = "GATEWAY_TIMEOUT"
    
    # AI Engine specific errors
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_NOT_FOUND = "PROVIDER_NOT_FOUND"
    PROVIDER_DISABLED = "PROVIDER_DISABLED"
    PROVIDER_FLAGGED = "PROVIDER_FLAGGED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
    PROVIDER_QUOTA_EXCEEDED = "PROVIDER_QUOTA_EXCEEDED"
    
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    
    NO_PROVIDERS_AVAILABLE = "NO_PROVIDERS_AVAILABLE"
    ALL_PROVIDERS_FAILED = "ALL_PROVIDERS_FAILED"
    
    CHAT_NOT_FOUND = "CHAT_NOT_FOUND"
    MESSAGE_NOT_FOUND = "MESSAGE_NOT_FOUND"
    
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    
    CACHE_ERROR = "CACHE_ERROR"
    
    WORKFLOW_NOT_FOUND = "WORKFLOW_NOT_FOUND"
    WORKFLOW_EXECUTION_FAILED = "WORKFLOW_EXECUTION_FAILED"
    
    PLUGIN_NOT_FOUND = "PLUGIN_NOT_FOUND"
    PLUGIN_LOAD_FAILED = "PLUGIN_LOAD_FAILED"
    
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"


@dataclass
class ErrorResponse:
    """Standardized error response"""
    error: str
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict:
        result = {
            "error": self.error,
            "code": self.code.value,
            "message": self.message
        }
        if self.details:
            result["details"] = self.details
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result


class ErrorFactory:
    """Factory for creating standardized errors"""
    
    @staticmethod
    def provider_not_found(provider: str) -> ErrorResponse:
        return ErrorResponse(
            error="Provider Not Found",
            code=ErrorCode.PROVIDER_NOT_FOUND,
            message=f"Provider '{provider}' not found in configuration",
            suggestion="Check available providers with GET /api/providers"
        )
    
    @staticmethod
    def model_not_found(model: str) -> ErrorResponse:
        return ErrorResponse(
            error="Model Not Found",
            code=ErrorCode.MODEL_NOT_FOUND,
            message=f"Model '{model}' not available in any provider",
            suggestion="Check available models with GET /v1/models"
        )
    
    @staticmethod
    def no_providers() -> ErrorResponse:
        return ErrorResponse(
            error="No Providers Available",
            code=ErrorCode.NO_PROVIDERS_AVAILABLE,
            message="No AI providers are currently available",
            suggestion="Configure at least one provider in config.py"
        )
    
    @staticmethod
    def provider_failed(provider: str, reason: str) -> ErrorResponse:
        return ErrorResponse(
            error="Provider Error",
            code=ErrorCode.PROVIDER_ERROR,
            message=f"Provider '{provider}' failed: {reason}",
            details={"provider": provider, "reason": reason}
        )
    
    @staticmethod
    def chat_not_found(chat_id: int) -> ErrorResponse:
        return ErrorResponse(
            error="Chat Not Found",
            code=ErrorCode.CHAT_NOT_FOUND,
            message=f"Chat with ID {chat_id} not found"
        )
    
    @staticmethod
    def rate_limited(retry_after: int = 60) -> ErrorResponse:
        return ErrorResponse(
            error="Rate Limited",
            code=ErrorCode.RATE_LIMITED,
            message="Too many requests",
            details={"retry_after": retry_after},
            suggestion=f"Wait {retry_after} seconds before retrying"
        )
    
    @staticmethod
    def unauthorized(detail: str = None) -> ErrorResponse:
        return ErrorResponse(
            error="Unauthorized",
            code=ErrorCode.UNAUTHORIZED,
            message=detail or "Authentication required",
            suggestion="Provide a valid API key in X-API-Key header"
        )
    
    @staticmethod
    def forbidden(detail: str = None) -> ErrorResponse:
        return ErrorResponse(
            error="Forbidden",
            code=ErrorCode.FORBIDDEN,
            message=detail or "Insufficient permissions"
        )
    
    @staticmethod
    def internal_error(detail: str = None) -> ErrorResponse:
        return ErrorResponse(
            error="Internal Error",
            code=ErrorCode.INTERNAL_ERROR,
            message=detail or "An internal error occurred"
        )
    
    @staticmethod
    def circuit_breaker_open(provider: str) -> ErrorResponse:
        return ErrorResponse(
            error="Circuit Breaker Open",
            code=ErrorCode.CIRCUIT_BREAKER_OPEN,
            message=f"Circuit breaker is open for provider '{provider}'",
            suggestion="Wait for the circuit to recover or try another provider"
        )


# HTTP status code mapping
ERROR_STATUS_CODES = {
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.UNPROCESSABLE: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.NOT_IMPLEMENTED: 501,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.GATEWAY_TIMEOUT: 504,
}


def get_http_status_code(error_code: ErrorCode) -> int:
    """Get HTTP status code for an error code"""
    return ERROR_STATUS_CODES.get(error_code, 500)
