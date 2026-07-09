import httpx
import pytest
from tests.server import DEMO_KEYS, MOCK_PROVIDER_BASE, start, stop, wait_ready


@pytest.fixture(scope="module")
def mock_server():
    proc = start()
    wait_ready()
    yield
    stop(proc)


def test_health(mock_server):
    r = httpx.get(f"{MOCK_PROVIDER_BASE}/health")
    assert r.status_code == 200


def test_alpha_key_succeeds(mock_server):
    r = httpx.post(
        f"{MOCK_PROVIDER_BASE}/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEMO_KEYS['alpha']}"},
        json={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    assert "alpha-ok" in r.json()["choices"][0]["message"]["content"]


def test_beta_key_rate_limited(mock_server):
    r = httpx.post(
        f"{MOCK_PROVIDER_BASE}/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEMO_KEYS['beta']}"},
        json={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 429


def test_gamma_key_unauthorized(mock_server):
    r = httpx.post(
        f"{MOCK_PROVIDER_BASE}/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEMO_KEYS['gamma']}"},
        json={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401