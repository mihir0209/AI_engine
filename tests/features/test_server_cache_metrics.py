"""Cache and metrics endpoint tests."""
import pytest


@pytest.mark.integration
def test_cache_stats_endpoint(server_client):
    resp = server_client.get("/api/cache/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "lru_cache" in data
    assert "deduplicator" in data
    assert "hit_rate" in data["lru_cache"]


@pytest.mark.integration
def test_cache_clear_endpoint(server_client):
    resp = server_client.get("/api/cache/clear")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"


@pytest.mark.integration
def test_metrics_summary_endpoint(server_client):
    server_client.get("/health")
    resp = server_client.get("/api/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data
    assert "successful" in data
    assert "failed" in data


@pytest.mark.integration
def test_latency_endpoint(server_client):
    resp = server_client.get("/api/latency")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


@pytest.mark.integration
def test_rate_limits_endpoint(server_client):
    resp = server_client.get("/api/rate-limits")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    if data:
        sample = next(iter(data.values()))
        assert "requests_made" in sample
        assert "available" in sample