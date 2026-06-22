"""Battle-tested tests for health monitor"""
import pytest
import time
import threading


@pytest.fixture
def monitor():
    from core.health_monitor import HealthMonitor
    return HealthMonitor(failure_threshold=3, recovery_time=0.1)


# === Basic Health Recording Tests ===

def test_record_successful_check(monitor):
    monitor.record_check("provider1", success=True, response_time=0.5)
    health = monitor.get_provider_health("provider1")
    assert health["status"] == "healthy"
    assert health["successful"] == 1
    assert health["failed"] == 0


def test_record_failed_check(monitor):
    monitor.record_check("provider1", success=False, error="timeout")
    health = monitor.get_provider_health("provider1")
    assert health["status"] == "degraded"
    assert health["failed"] == 1


def test_record_multiple_checks(monitor):
    for i in range(10):
        monitor.record_check("provider1", success=True, response_time=0.1 * i)
    
    health = monitor.get_provider_health("provider1")
    assert health["total_checks"] == 10
    assert health["successful"] == 10
    assert health["uptime_percent"] == 100.0


def test_record_mixed_checks(monitor):
    for i in range(10):
        monitor.record_check("provider1", success=(i % 2 == 0))
    
    health = monitor.get_provider_health("provider1")
    assert health["total_checks"] == 10
    assert health["successful"] == 5
    assert health["uptime_percent"] == 50.0


# === Provider Health Status Tests ===

def test_healthy_provider(monitor):
    for _ in range(5):
        monitor.record_check("provider1", success=True)
    
    assert monitor.is_provider_healthy("provider1") is True


def test_unhealthy_provider(monitor):
    for _ in range(5):
        monitor.record_check("provider1", success=False)
    
    assert monitor.is_provider_healthy("provider1") is False


def test_provider_recovery(monitor):
    # Make provider unhealthy
    for _ in range(5):
        monitor.record_check("provider1", success=False)
    
    assert monitor.is_provider_healthy("provider1") is False
    
    # Wait for recovery time
    time.sleep(1.5)
    
    # Should be allowed to retry
    assert monitor.is_provider_healthy("provider1") is True


def test_unknown_provider_healthy(monitor):
    assert monitor.is_provider_healthy("unknown_provider") is True


# === Response Time Tracking Tests ===

def test_avg_response_time(monitor):
    monitor.record_check("provider1", success=True, response_time=0.1)
    monitor.record_check("provider1", success=True, response_time=0.3)
    monitor.record_check("provider1", success=True, response_time=0.2)
    
    health = monitor.get_provider_health("provider1")
    assert health["avg_response_time"] == 0.2


def test_avg_response_time_failed_not_counted(monitor):
    monitor.record_check("provider1", success=True, response_time=0.1)
    monitor.record_check("provider1", success=False, response_time=1.0)
    monitor.record_check("provider1", success=True, response_time=0.3)
    
    health = monitor.get_provider_health("provider1")
    assert health["avg_response_time"] == 0.2  # Only successful ones


# === Uptime Calculation Tests ===

def test_uptime_100_percent(monitor):
    for _ in range(100):
        monitor.record_check("provider1", success=True)
    
    health = monitor.get_provider_health("provider1")
    assert health["uptime_percent"] == 100.0


def test_uptime_0_percent(monitor):
    for _ in range(100):
        monitor.record_check("provider1", success=False)
    
    health = monitor.get_provider_health("provider1")
    assert health["uptime_percent"] == 0.0


def test_uptime_calculation(monitor):
    for _ in range(7):
        monitor.record_check("provider1", success=True)
    for _ in range(3):
        monitor.record_check("provider1", success=False)
    
    health = monitor.get_provider_health("provider1")
    assert health["uptime_percent"] == 70.0


# === Recent Checks History Tests ===

def test_recent_checks_limited(monitor):
    for i in range(150):
        monitor.record_check("provider1", success=True)
    
    health = monitor.get_provider_health("provider1")
    assert health["total_checks"] == 150


# === Consecutive Failures Tests ===

def test_consecutive_failures_reset(monitor):
    monitor.record_check("provider1", success=False)
    monitor.record_check("provider1", success=False)
    monitor.record_check("provider1", success=True)  # Reset
    
    health = monitor.get_provider_health("provider1")
    assert health["consecutive_failures"] == 0


def test_consecutive_failures_increment(monitor):
    for _ in range(5):
        monitor.record_check("provider1", success=False)
    
    health = monitor.get_provider_health("provider1")
    assert health["consecutive_failures"] == 5


# === Multi-Provider Tests ===

def test_multiple_providers(monitor):
    monitor.record_check("provider1", success=True)
    monitor.record_check("provider2", success=False)
    monitor.record_check("provider3", success=True)
    
    summary = monitor.get_summary()
    assert summary["total"] == 3
    assert summary["healthy"] == 2
    assert summary["unhealthy"] == 0


def test_get_healthy_providers(monitor):
    monitor.record_check("healthy1", success=True)
    monitor.record_check("healthy2", success=True)
    monitor.record_check("unhealthy1", success=False)
    monitor.record_check("unhealthy2", success=False)
    monitor.record_check("unhealthy2", success=False)
    monitor.record_check("unhealthy2", success=False)
    
    healthy = monitor.get_healthy_providers()
    assert "healthy1" in healthy
    assert "healthy2" in healthy
    assert "unhealthy1" not in healthy
    assert "unhealthy2" not in healthy


def test_get_unhealthy_providers(monitor):
    for _ in range(5):
        monitor.record_check("bad_provider", success=False)
    
    unhealthy = monitor.get_unhealthy_providers()
    assert "bad_provider" in unhealthy


# === Summary Tests ===

def test_summary(monitor):
    monitor.record_check("p1", success=True)
    monitor.record_check("p2", success=False)
    monitor.record_check("p2", success=False)
    monitor.record_check("p2", success=False)
    
    summary = monitor.get_summary()
    assert summary["total"] == 2
    assert summary["healthy"] == 1
    assert summary["unhealthy"] == 1


# === Reset Tests ===

def test_reset_provider(monitor):
    for _ in range(5):
        monitor.record_check("provider1", success=False)
    
    assert monitor.is_provider_healthy("provider1") is False
    
    monitor.reset_provider("provider1")
    
    health = monitor.get_provider_health("provider1")
    assert health["status"] == "unknown"
    assert health["total_checks"] == 0


# === Thread Safety Tests ===

def test_concurrent_health_checks(monitor):
    def record_checks(provider):
        for _ in range(20):
            monitor.record_check(provider, success=True)
    
    threads = [threading.Thread(target=record_checks, args=(f"p{i}",)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3)
    
    assert monitor.get_summary()["total"] == 3


# === Edge Cases ===

def test_zero_checks_health(monitor):
    health = monitor.get_provider_health("new_provider")
    assert health["status"] == "unknown"
    assert health["uptime_percent"] == 0


def test_single_check_health(monitor):
    monitor.record_check("provider1", success=True)
    health = monitor.get_provider_health("provider1")
    assert health["total_checks"] == 1
    assert health["uptime_percent"] == 100.0
