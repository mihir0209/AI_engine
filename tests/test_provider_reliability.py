"""Tests for provider failure classification and fallback policy."""

import pytest


@pytest.mark.parametrize(
    "error_type",
    ["rate_limit", "auth_error", "quota_exceeded", "service_unavailable", "server_error", "network_error"],
)
def test_provider_failure_policy_retries_transient_or_routeable_errors(error_type):
    from core.provider_reliability import should_retry_provider

    assert should_retry_provider(error_type) is True


def test_provider_failure_policy_does_not_retry_bad_request():
    from core.provider_reliability import should_retry_provider

    assert should_retry_provider("bad_request") is False


def test_provider_failure_policy_retries_unknown_stream_errors():
    from core.provider_reliability import should_retry_provider

    assert should_retry_provider("unknown") is True


def test_provider_failure_policy_preserves_cancellation():
    from core.provider_reliability import should_retry_provider

    assert should_retry_provider("cancelled") is False
