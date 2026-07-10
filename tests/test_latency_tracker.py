"""Tests for latency tracker"""


def test_record_latency():
    from core.latency_tracker import LatencyTracker
    tracker = LatencyTracker()

    tracker.record("provider1", 100, True)
    tracker.record("provider1", 200, True)
    tracker.record("provider1", 150, True)

    stats = tracker.get_stats("provider1")
    assert stats["total_requests"] == 3
    assert stats["avg_latency_ms"] == 150.0


def test_get_avg_latency():
    from core.latency_tracker import LatencyTracker
    tracker = LatencyTracker()

    tracker.record("provider1", 100, True)
    tracker.record("provider1", 200, True)

    avg = tracker.get_avg_latency("provider1")
    assert avg == 150.0


def test_get_p95_latency():
    from core.latency_tracker import LatencyTracker
    tracker = LatencyTracker()

    # Add 20 measurements
    for i in range(20):
        tracker.record("provider1", 100 + i * 10, True)

    p95 = tracker.get_p95_latency("provider1")
    assert p95 > 0


def test_is_slow():
    from core.latency_tracker import LatencyTracker
    tracker = LatencyTracker(slow_threshold_ms=500)

    tracker.record("fast_provider", 100, True)
    tracker.record("slow_provider", 1000, True)

    assert tracker.is_slow("fast_provider") is False
    assert tracker.is_slow("slow_provider") is True


def test_priority_adjustment():
    from core.latency_tracker import LatencyTracker
    tracker = LatencyTracker()

    # Fast provider
    for _ in range(5):
        tracker.record("fast", 100, True)

    # Slow provider
    for _ in range(5):
        tracker.record("slow", 6000, True)

    fast_adj = tracker.get_priority_adjustment("fast")
    slow_adj = tracker.get_priority_adjustment("slow")

    assert fast_adj < slow_adj  # Fast provider gets lower adjustment


def test_get_stats_all():
    from core.latency_tracker import LatencyTracker
    tracker = LatencyTracker()

    tracker.record("p1", 100, True)
    tracker.record("p2", 200, True)

    stats = tracker.get_stats()
    assert "p1" in stats
    assert "p2" in stats


def test_unknown_provider():
    from core.latency_tracker import LatencyTracker
    tracker = LatencyTracker()

    avg = tracker.get_avg_latency("unknown")
    assert avg == 0.0

    stats = tracker.get_stats("unknown")
    assert stats == {}


def test_model_tracking():
    from core.latency_tracker import LatencyTracker
    tracker = LatencyTracker()

    tracker.record("provider1", 100, True, model="gpt-4")
    tracker.record("provider1", 150, True, model="claude-3")

    stats = tracker.get_stats("provider1")
    assert "gpt-4" in stats["models"]
    assert "claude-3" in stats["models"]
