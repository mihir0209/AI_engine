"""Tests for request middleware and tracking"""
import pytest
import time


# === Metrics Collector Tests ===

def test_metrics_collector_init():
    from core.middleware import MetricsCollector
    mc = MetricsCollector()
    assert len(mc.requests) == 0


def test_record_request():
    from core.middleware import MetricsCollector, RequestMetrics
    mc = MetricsCollector()

    metrics = RequestMetrics(
        request_id="test_1",
        endpoint="/api/test",
        method="GET",
        start_time=time.time(),
        end_time=time.time() + 0.1,
        status_code=200
    )
    mc.record_request(metrics)

    assert len(mc.requests) == 1
    assert mc.requests[0].duration_ms > 0


def test_get_endpoint_stats():
    from core.middleware import MetricsCollector, RequestMetrics
    mc = MetricsCollector()

    for i in range(5):
        metrics = RequestMetrics(
            request_id=f"test_{i}",
            endpoint="/api/test",
            method="GET",
            start_time=time.time(),
            end_time=time.time() + 0.01,
            status_code=200
        )
        mc.record_request(metrics)

    stats = mc.get_endpoint_stats("/api/test")
    assert stats["count"] == 5
    assert stats["avg_ms"] > 0


def test_get_overall_stats():
    from core.middleware import MetricsCollector, RequestMetrics
    mc = MetricsCollector()

    for i in range(10):
        metrics = RequestMetrics(
            request_id=f"test_{i}",
            endpoint="/api/test",
            method="GET",
            start_time=time.time(),
            end_time=time.time() + 0.01,
            status_code=200 if i < 8 else 500
        )
        mc.record_request(metrics)

    stats = mc.get_overall_stats()
    assert stats["total_requests"] == 10
    assert stats["successful"] == 8
    assert stats["failed"] == 2


def test_get_recent_requests():
    from core.middleware import MetricsCollector, RequestMetrics
    mc = MetricsCollector()

    for i in range(3):
        metrics = RequestMetrics(
            request_id=f"test_{i}",
            endpoint="/api/test",
            method="GET",
            start_time=time.time()
        )
        mc.record_request(metrics)

    recent = mc.get_recent_requests(limit=2)
    assert len(recent) == 2


# === Request Tracker Tests ===

def test_request_tracker_start():
    from core.middleware import RequestTracker
    metrics = RequestTracker.start_request("/api/test", "POST")

    assert metrics.request_id is not None
    assert metrics.endpoint == "/api/test"
    assert metrics.method == "POST"


def test_request_tracker_get_current():
    from core.middleware import RequestTracker
    RequestTracker.start_request("/api/test")

    current = RequestTracker.get_current()
    assert current is not None


def test_request_tracker_end():
    from core.middleware import RequestTracker
    RequestTracker.start_request("/api/test")
    RequestTracker.end_request(status_code=200)

    current = RequestTracker.get_current()
    assert current.status_code == 200
    assert current.end_time is not None


def test_request_tracker_set_provider():
    from core.middleware import RequestTracker
    RequestTracker.start_request("/api/test")
    RequestTracker.set_provider("openai", "gpt-4")

    current = RequestTracker.get_current()
    assert current.provider == "openai"
    assert current.model == "gpt-4"


def test_request_tracker_set_tokens():
    from core.middleware import RequestTracker
    RequestTracker.start_request("/api/test")
    RequestTracker.set_tokens(150, 0.003)

    current = RequestTracker.get_current()
    assert current.tokens_used == 150
    assert current.cost == 0.003


# === Tracked Request Decorator Tests ===

def test_tracked_request_decorator():
    from core.middleware import tracked_request

    @tracked_request("/api/test")
    def test_func():
        return "success"

    result = test_func()
    assert result == "success"


def test_tracked_request_on_error():
    from core.middleware import tracked_request

    @tracked_request("/api/error")
    def failing_func():
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        failing_func()
