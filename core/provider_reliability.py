"""Shared provider failure policy for chat and streaming routes."""

_RETRYABLE_ERRORS = frozenset(
    {
        "rate_limit",
        "auth_error",
        "quota_exceeded",
        "service_unavailable",
        "server_error",
        "network_error",
        "unknown",
    }
)


def should_retry_provider(error_type: str) -> bool:
    """Return whether routing should continue with another provider."""
    return error_type in _RETRYABLE_ERRORS
