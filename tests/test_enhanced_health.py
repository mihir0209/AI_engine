"""Tests for enhanced health checks and per-user rate limiting"""
import time


# === Health Check Registry Tests ===

def test_register_check():
    from core.enhanced_health import HealthCheckRegistry
    hr = HealthCheckRegistry()

    hr.register("test", lambda: True)
    assert "test" in hr.checks


def test_run_check_healthy():
    from core.enhanced_health import HealthCheckRegistry
    hr = HealthCheckRegistry()

    hr.register("healthy_check", lambda: True)
    result = hr.run_check("healthy_check")
    assert result["status"] == "healthy"


def test_run_check_unhealthy():
    from core.enhanced_health import HealthCheckRegistry
    hr = HealthCheckRegistry()

    hr.register("unhealthy_check", lambda: False)
    result = hr.run_check("unhealthy_check")
    assert result["status"] == "unhealthy"


def test_run_check_error():
    from core.enhanced_health import HealthCheckRegistry
    hr = HealthCheckRegistry()

    def error_check():
        raise Exception("Check failed")

    hr.register("error_check", error_check)
    result = hr.run_check("error_check")
    assert result["status"] == "error"


def test_run_check_not_found():
    from core.enhanced_health import HealthCheckRegistry
    hr = HealthCheckRegistry()

    result = hr.run_check("nonexistent")
    assert result["status"] == "unknown"


def test_run_all_checks():
    from core.enhanced_health import HealthCheckRegistry
    hr = HealthCheckRegistry()

    hr.register("check1", lambda: True)
    hr.register("check2", lambda: True)

    results = hr.run_all()
    assert results["status"] == "healthy"
    assert len(results["checks"]) == 2


def test_run_all_checks_degraded():
    from core.enhanced_health import HealthCheckRegistry
    hr = HealthCheckRegistry()

    hr.register("good", lambda: True)
    hr.register("bad", lambda: False)

    results = hr.run_all()
    assert results["status"] == "degraded"


def test_get_last_results():
    from core.enhanced_health import HealthCheckRegistry
    hr = HealthCheckRegistry()

    hr.register("test", lambda: True)
    hr.run_check("test")

    results = hr.get_last_results()
    assert "test" in results
    assert results["test"]["status"] == "healthy"


# === Per-User Rate Limiter Tests ===

def test_rate_limiter_allows_request():
    from core.enhanced_health import PerUserRateLimiter
    rl = PerUserRateLimiter(default_rate=10, default_burst=10)

    allowed, info = rl.allow_request("user_1")
    assert allowed is True
    assert info["remaining"] == 9


def test_rate_limiter_blocks_request():
    from core.enhanced_health import PerUserRateLimiter
    rl = PerUserRateLimiter(default_rate=1, default_burst=2)

    rl.allow_request("user_1")
    rl.allow_request("user_1")
    allowed, info = rl.allow_request("user_1")
    assert allowed is False
    assert "retry_after" in info


def test_rate_limiter_refill():
    from core.enhanced_health import PerUserRateLimiter
    rl = PerUserRateLimiter(default_rate=60, default_burst=2)  # 1 token per second

    # Use up all tokens
    rl.allow_request("user_1")
    rl.allow_request("user_1")

    # Wait for refill (at least 1 second for 1 token at 60/min = 1/sec)
    time.sleep(1.5)

    # Should have at least 1 token refilled
    allowed, info = rl.allow_request("user_1")
    assert allowed is True


def test_rate_limiter_configure_user():
    from core.enhanced_health import PerUserRateLimiter
    rl = PerUserRateLimiter(default_rate=10, default_burst=5)

    rl.configure_user("vip_user", rate=100, burst=50)

    # VIP user should have higher limits
    for _ in range(20):
        allowed, _ = rl.allow_request("vip_user")
        assert allowed is True


def test_rate_limiter_get_usage():
    from core.enhanced_health import PerUserRateLimiter
    rl = PerUserRateLimiter(default_rate=10, default_burst=10)

    rl.allow_request("user_1")
    rl.allow_request("user_1")

    usage = rl.get_usage("user_1")
    assert usage["used"] == 2
    assert usage["remaining"] == 8


def test_rate_limiter_reset():
    from core.enhanced_health import PerUserRateLimiter
    rl = PerUserRateLimiter(default_rate=1, default_burst=1)

    rl.allow_request("user_1")
    allowed, _ = rl.allow_request("user_1")
    assert allowed is False

    rl.reset("user_1")
    allowed, _ = rl.allow_request("user_1")
    assert allowed is True


def test_rate_limiter_separate_users():
    from core.enhanced_health import PerUserRateLimiter
    rl = PerUserRateLimiter(default_rate=10, default_burst=2)

    rl.allow_request("user_1")
    rl.allow_request("user_1")

    # user_2 should still have full quota
    allowed, _ = rl.allow_request("user_2")
    assert allowed is True
