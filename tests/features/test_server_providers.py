"""Provider management endpoint tests."""
import pytest


@pytest.mark.integration
def test_get_providers_sanitized(server_client):
    resp = server_client.get("/api/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert isinstance(providers, dict)
    assert len(providers) > 0
    for name, config in providers.items():
        assert "id" in config
        assert "enabled" in config
        assert "api_keys" not in config
        assert name in providers


@pytest.mark.integration
def test_toggle_provider_round_trip(server_client):
    providers_resp = server_client.get("/api/providers")
    provider_name = next(
        name for name, cfg in providers_resp.json().items() if cfg.get("enabled", True)
    )
    original = providers_resp.json()[provider_name]["enabled"]

    disable_resp = server_client.post(
        f"/api/providers/{provider_name}/toggle",
        json={"enabled": not original},
    )
    assert disable_resp.status_code == 200

    restore_resp = server_client.post(
        f"/api/providers/{provider_name}/toggle",
        json={"enabled": original},
    )
    assert restore_resp.status_code == 200


@pytest.mark.integration
def test_toggle_provider_not_found(server_client):
    resp = server_client.post(
        "/api/providers/nonexistent-provider/toggle",
        json={"enabled": True},
    )
    assert resp.status_code in (404, 500)


@pytest.mark.integration
def test_roll_key_endpoint(server_client, mock_provider_server, reset_server_test_harness_keys):
    resp = server_client.post("/api/providers/test_harness/roll-key")
    assert resp.status_code == 200
    message = resp.json()["message"].lower()
    assert "roll" in message


@pytest.mark.integration
def test_provider_models_discovery(
    server_client, mock_provider_server, reset_server_test_harness_keys
):
    resp = server_client.get("/api/providers/test_harness/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "test_harness"
    assert "models" in data
    model_ids = [m.get("id") for m in data["models"]]
    assert "test-model" in model_ids


@pytest.mark.integration
def test_provider_health_summary(server_client):
    resp = server_client.get("/api/providers/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "summary" in data
    assert "healthy" in data["summary"]
    assert data["summary"]["total_enabled"] >= data["summary"]["healthy"]


@pytest.mark.integration
def test_capabilities_endpoint(server_client):
    resp = server_client.get("/api/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data or "vision_providers" in data


@pytest.mark.integration
def test_vision_providers_endpoint(server_client):
    resp = server_client.get("/api/capabilities/vision")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)


@pytest.mark.integration
def test_check_image_compatibility(server_client):
    resp = server_client.get("/api/capabilities/check-image/gemini?model=gemini-2.5-flash")
    assert resp.status_code == 200
    data = resp.json()
    assert data["compatible"] is True
    assert "reason" in data


@pytest.mark.integration
def test_test_model_via_harness(
    server_client, mock_provider_server, reset_server_test_harness_keys
):
    resp = server_client.post(
        "/api/test-model",
        json={
            "provider": "test_harness",
            "model": "test-model",
            "message": "ping",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["provider"] == "test_harness"
    assert "alpha-ok" in data["response"]
