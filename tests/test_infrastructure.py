"""Tests for infrastructure utilities"""
import pytest
import time


# === Circuit Breaker Tests ===

def test_circuit_breaker_initial_state():
    from core.infrastructure import CircuitBreaker, CircuitState
    cb = CircuitBreaker("test", failure_threshold=3)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_opens_after_failures():
    from core.infrastructure import CircuitBreaker, CircuitState
    cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=1)

    for _ in range(3):
        cb.record_failure()

    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


def test_circuit_breaker_half_open_after_timeout():
    from core.infrastructure import CircuitBreaker, CircuitState
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)

    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    time.sleep(0.2)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN


def test_circuit_breaker_closes_after_recovery():
    from core.infrastructure import CircuitBreaker, CircuitState
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1, half_open_max_calls=2)

    cb.record_failure()
    cb.record_failure()
    time.sleep(0.2)

    cb.can_execute()  # Transition to half_open
    cb.record_success()
    cb.record_success()  # Should close

    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_resets_on_success():
    from core.infrastructure import CircuitBreaker
    cb = CircuitBreaker("test", failure_threshold=3)

    cb.record_failure()
    cb.record_failure()
    cb.record_success()  # Reset failure count

    assert cb.failure_count == 0


def test_circuit_breaker_get_state():
    from core.infrastructure import CircuitBreaker
    cb = CircuitBreaker("test")
    state = cb.get_state()

    assert state["name"] == "test"
    assert state["state"] == "closed"


def test_circuit_breaker_reset():
    from core.infrastructure import CircuitBreaker, CircuitState
    cb = CircuitBreaker("test", failure_threshold=2)

    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED


# === Retry Handler Tests ===

def test_retry_handler_calculate_delay():
    from core.infrastructure import RetryHandler
    rh = RetryHandler(base_delay=1.0, exponential_base=2.0, jitter=False)

    assert rh.calculate_delay(0) == 1.0
    assert rh.calculate_delay(1) == 2.0
    assert rh.calculate_delay(2) == 4.0


def test_retry_handler_max_delay():
    from core.infrastructure import RetryHandler
    rh = RetryHandler(base_delay=1.0, max_delay=5.0, jitter=False)

    assert rh.calculate_delay(10) == 5.0


def test_retry_handler_execute_success():
    from core.infrastructure import RetryHandler
    rh = RetryHandler(max_retries=3)

    call_count = 0
    def success_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = rh.execute_with_retry(success_func)
    assert result == "success"
    assert call_count == 1


def test_retry_handler_execute_with_retries():
    from core.infrastructure import RetryHandler
    rh = RetryHandler(max_retries=2, base_delay=0.01, jitter=False)

    call_count = 0
    def failing_then_success():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Not yet")
        return "success"

    result = rh.execute_with_retry(failing_then_success)
    assert result == "success"
    assert call_count == 3


def test_retry_handler_execute_all_fail():
    from core.infrastructure import RetryHandler
    rh = RetryHandler(max_retries=2, base_delay=0.01, jitter=False)

    def always_fail():
        raise ValueError("Always fails")

    with pytest.raises(ValueError):
        rh.execute_with_retry(always_fail)


# === Health Checker Tests ===

def test_health_checker_register_and_run():
    from core.infrastructure import HealthChecker
    hc = HealthChecker()

    hc.register_check("test", lambda: True)
    results = hc.run_checks()

    assert results["status"] == "healthy"
    assert "test" in results["checks"]


def test_health_checker_unhealthy():
    from core.infrastructure import HealthChecker
    hc = HealthChecker()

    hc.register_check("failing", lambda: False)
    results = hc.run_checks()

    assert results["status"] == "degraded"


def test_health_checker_error():
    from core.infrastructure import HealthChecker
    hc = HealthChecker()

    def error_check():
        raise Exception("Check failed")

    hc.register_check("error", error_check)
    results = hc.run_checks()

    assert results["status"] == "degraded"
    assert results["checks"]["error"]["status"] == "error"


def test_health_checker_get_last_results():
    from core.infrastructure import HealthChecker
    hc = HealthChecker()
    hc.register_check("test", lambda: True)

    hc.run_checks()
    last = hc.get_last_results()

    assert "test" in last
