"""Server health and monitoring endpoint tests."""
import pytest


@pytest.mark.integration
def test_health_returns_healthy(server_client):
    resp = server_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.integration
def test_metrics_prometheus_format(server_client):
    resp = server_client.get("/metrics")
    assert resp.status_code == 200
    assert "ai_engine_requests_total" in resp.text
    assert "ai_engine_request_latency_seconds" in resp.text


@pytest.mark.integration
def test_health_summary_structure(server_client):
    resp = server_client.get("/api/health/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "healthy" in data
    assert "degraded" in data
    assert "unhealthy" in data
    assert data["total"] >= data["healthy"]


@pytest.mark.integration
def test_health_providers_monitoring(server_client):
    from core.health_monitor import health_monitor

    health_monitor.record_check("test_harness", success=True, response_time=0.05)
    resp = server_client.get("/api/health/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "test_harness" in data
    harness = data["test_harness"]
    assert harness["status"] in ("healthy", "degraded", "unhealthy", "unknown")
    assert "uptime_percent" in harness