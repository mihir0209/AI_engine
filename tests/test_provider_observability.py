"""Tests for the normalized provider observability read model."""


def test_provider_snapshot_normalizes_existing_reliability_signals(monkeypatch):
    from core import provider_observability
    from core.health_monitor import HealthMonitor
    from core.infrastructure import CircuitBreaker, circuit_breakers
    from core.latency_tracker import LatencyTracker
    from core.rate_limit_manager import RateLimitManager
    from core.usage_tracker import UsageTracker

    health = HealthMonitor()
    health.record_check("alpha", success=True, response_time=0.25)
    health.record_check("alpha", success=False, error="timeout", status_code=504)
    latency = LatencyTracker()
    latency.record("alpha", 120, success=True)
    latency.record("alpha", 480, success=False)
    rate_limits = RateLimitManager()
    rate_limits.record_request("alpha")
    rate_limits.mark_rate_limited("alpha", retry_after=30)
    usage = UsageTracker()
    usage.record("alpha", "model-a", success=True, response_time=0.12)
    usage.record("alpha", "model-a", success=False, response_time=0.48)

    breaker_name = "provider:alpha"
    breaker = CircuitBreaker(breaker_name)
    breaker.record_failure()
    circuit_breakers[breaker_name] = breaker
    monkeypatch.setattr(provider_observability, "health_monitor", health)
    monkeypatch.setattr(provider_observability, "latency_tracker", latency)
    monkeypatch.setattr(provider_observability, "rate_limit_manager", rate_limits)
    monkeypatch.setattr(provider_observability, "usage_tracker", usage)

    try:
        snapshot = provider_observability.get_provider_snapshot("alpha")
    finally:
        circuit_breakers.pop(breaker_name, None)

    assert snapshot["provider"] == "alpha"
    assert snapshot["health"]["total_checks"] == 2
    assert snapshot["health"]["successful"] == 1
    assert snapshot["health"]["failed"] == 1
    assert snapshot["latency"]["avg_latency_ms"] == 300.0
    assert snapshot["latency"]["total_requests"] == 2
    assert snapshot["rate_limit"]["is_limited"] is True
    assert snapshot["rate_limit"]["requests_made"] == 1
    assert snapshot["usage"]["requests"] == 2
    assert snapshot["usage"]["successful"] == 1
    assert snapshot["usage"]["success_rate"] == 50.0
    assert snapshot["circuit"]["state"] == "closed"
    assert snapshot["circuit"]["failure_count"] == 1


def test_unknown_provider_snapshot_uses_defaults_without_creating_state():
    from core import provider_observability
    from core.infrastructure import circuit_breakers
    from core.rate_limit_manager import rate_limit_manager

    provider = "provider-that-does-not-exist"
    before_circuits = set(circuit_breakers)
    before_rate_limits = set(rate_limit_manager.providers)
    snapshot = provider_observability.get_provider_snapshot(provider)

    assert set(circuit_breakers) == before_circuits
    assert set(rate_limit_manager.providers) == before_rate_limits
    assert snapshot == {
        "provider": provider,
        "health": {
            "status": "unknown",
            "uptime_percent": 0.0,
            "total_checks": 0,
            "successful": 0,
            "failed": 0,
            "consecutive_failures": 0,
            "last_check": None,
        },
        "latency": {"avg_latency_ms": 0.0, "p95_latency_ms": 0.0, "total_requests": 0},
        "rate_limit": {
            "is_limited": False,
            "available": True,
            "requests_made": 0,
            "requests_limit": 60,
            "retry_after": 0,
        },
        "usage": {
            "requests": 0,
            "successful": 0,
            "failed": 0,
            "success_rate": 0,
            "avg_response_time": 0,
        },
        "circuit": {
            "state": "unknown",
            "failure_count": 0,
            "success_count": 0,
            "last_failure_time": None,
            "last_state_change": None,
        },
    }


def test_get_all_provider_snapshots_preserves_requested_names():
    from core.provider_observability import get_all_provider_snapshots

    snapshots = get_all_provider_snapshots(["alpha", "beta"])

    assert list(snapshots) == ["alpha", "beta"]
    assert snapshots["alpha"]["provider"] == "alpha"
    assert snapshots["beta"]["provider"] == "beta"
