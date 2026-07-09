"""Platform status and configuration endpoint tests."""
import pytest


@pytest.mark.integration
def test_status_endpoint(server_client):
    resp = server_client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_providers"] >= data["enabled_providers"]
    assert "enabled_provider_list" in data
    assert "explanation" in data


@pytest.mark.integration
def test_statistics_endpoint(server_client):
    resp = server_client.get("/api/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "providers" in data
    assert "timestamp" in data
    assert "overall_success_rate" in data["summary"]


@pytest.mark.integration
def test_cdn_config_status(server_client):
    resp = server_client.get("/api/cdn-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "url" in data


@pytest.mark.integration
def test_version_endpoint(server_client):
    resp = server_client.get("/api/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "current" in data
    assert "supported" in data
    assert isinstance(data["supported"], list)


@pytest.mark.integration
def test_config_reload_endpoint(server_client):
    resp = server_client.post("/api/config/reload")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "reloaded"
    assert "providers" in data
    assert data["providers"] > 0