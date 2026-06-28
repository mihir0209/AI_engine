"""Exception hierarchy for AI Synapse SDK."""


class AIEngineError(Exception):
    """Base exception for AI Engine SDK."""
    def __init__(self, message=None, status_code=None, error_type=None, param=None, code=None):
        self.status_code = status_code
        self.error_type = error_type
        self.param = param
        self.code = code
        super().__init__(message or "An error occurred")


class OpenAIError(AIEngineError):
    """Error matching OpenAI SDK format."""
    pass


class BadRequestError(OpenAIError):
    def __init__(self, message=None, response=None, body=None, **kwargs):
        super().__init__(message, status_code=400, error_type="invalid_request_error", **kwargs)


class AuthenticationError(OpenAIError):
    def __init__(self, message=None, response=None, body=None, **kwargs):
        super().__init__(message, status_code=401, error_type="authentication_error", **kwargs)


class PermissionDeniedError(OpenAIError):
    def __init__(self, message=None, response=None, body=None, **kwargs):
        super().__init__(message, status_code=403, error_type="permission_error", **kwargs)


class NotFoundError(OpenAIError):
    def __init__(self, message=None, response=None, body=None, **kwargs):
        super().__init__(message, status_code=404, error_type="not_found_error", **kwargs)


class RateLimitError(OpenAIError):
    def __init__(self, message=None, response=None, body=None, **kwargs):
        super().__init__(message, status_code=429, error_type="rate_limit_error", **kwargs)


class InternalServerError(OpenAIError):
    def __init__(self, message=None, response=None, body=None, **kwargs):
        super().__init__(message, status_code=500, error_type="server_error", **kwargs)


class AnthropicError(AIEngineError):
    """Error matching Anthropic SDK format."""
    pass


class AnthropicBadRequestError(AnthropicError):
    def __init__(self, message=None):
        super().__init__(message, status_code=400, error_type="invalid_request_error")


class AnthropicAuthenticationError(AnthropicError):
    def __init__(self, message=None):
        super().__init__(message, status_code=401, error_type="authentication_error")


class AnthropicRateLimitError(AnthropicError):
    def __init__(self, message=None):
        super().__init__(message, status_code=429, error_type="rate_limit_error")


def raise_for_status(status_code, error_body):
    """Raise the appropriate exception for a given status code."""
    error_dict = error_body.get("error", {})
    message = error_dict.get("message", "Unknown error")
    error_type = error_dict.get("type", "unknown")
    param = error_dict.get("param")
    code = error_dict.get("code")

    exc_map = {
        400: BadRequestError,
        401: AuthenticationError,
        403: PermissionDeniedError,
        404: NotFoundError,
        429: RateLimitError,
        500: InternalServerError,
    }

    exc_cls = exc_map.get(status_code, OpenAIError)
    if exc_cls in (OpenAIError,):
        raise exc_cls(message=message, status_code=status_code, error_type=error_type, param=param, code=code)
    raise exc_cls(message=message, param=param, code=code)
