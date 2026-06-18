"""Tests for integration and load testing"""
import pytest
import time


# === Integration Tests ===

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from server import app
    return TestClient(app)


def test_health_check_integration(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_models_endpoint_integration(client):
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert "data" in data


def test_providers_endpoint_integration(client):
    resp = client.get("/api/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) > 0
    # Check sanitized output (no api_keys)
    for name, config in providers.items():
        assert "api_keys" not in config


def test_statistics_endpoint_integration(client):
    resp = client.get("/api/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "providers" in data


def test_status_endpoint_integration(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_providers" in data
    assert "enabled_providers" in data


def test_provider_health_integration(client):
    resp = client.get("/api/providers/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "summary" in data


def test_chat_lifecycle_integration(client):
    """Full chat lifecycle test"""
    # Create
    create_resp = client.post("/api/chat/chats", json={"title": "Integration Test"})
    assert create_resp.status_code == 200
    chat_id = create_resp.json()["chat_id"]

    # Get
    get_resp = client.get(f"/api/chat/chats/{chat_id}")
    assert get_resp.status_code == 200

    # Add message
    msg_resp = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Hello integration test"
    })
    assert msg_resp.status_code == 200

    # Search
    search_resp = client.post("/api/chat/search", json={"query": "integration"})
    assert search_resp.status_code == 200

    # Export
    export_resp = client.get(f"/api/chat/chats/{chat_id}/export")
    assert export_resp.status_code == 200

    # Delete
    delete_resp = client.delete(f"/api/chat/chats/{chat_id}")
    assert delete_resp.status_code == 200

    # Verify deleted
    get_resp = client.get(f"/api/chat/chats/{chat_id}")
    assert get_resp.status_code == 404


def test_search_integration(client):
    """Search functionality test"""
    # Create chat with messages
    create_resp = client.post("/api/chat/chats", json={"title": "Search Test"})
    chat_id = create_resp.json()["chat_id"]

    for word in ["apple", "banana", "cherry", "apple pie"]:
        client.post(f"/api/chat/chats/{chat_id}/messages", json={
            "role": "user", "content": f"I like {word}"
        })

    # Search
    search_resp = client.post("/api/chat/search", json={"query": "apple"})
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert results["total"] >= 2  # "apple" and "apple pie"


def test_branching_integration(client):
    """Branching functionality test"""
    create_resp = client.post("/api/chat/chats", json={"title": "Branch Test"})
    chat_id = create_resp.json()["chat_id"]

    # Add messages
    msg1 = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Start"
    }).json()["message_id"]

    client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "system", "content": "Response 1"
    })

    msg3 = client.post(f"/api/chat/chats/{chat_id}/messages", json={
        "role": "user", "content": "Continue"
    }).json()["message_id"]

    # Create branch from message 3
    branch_resp = client.post(f"/api/chat/chats/{chat_id}/branch/{msg3}")
    assert branch_resp.status_code == 200
    branch_id = branch_resp.json()["branch_id"]

    # Get branches
    branches_resp = client.get(f"/api/chat/chats/{chat_id}/branches")
    assert branches_resp.status_code == 200
    assert len(branches_resp.json()["branches"]) >= 1


# === Load Testing Tests ===

def test_load_tester_init():
    from load_test import LoadTester
    tester = LoadTester()
    assert len(tester.results) == 0


def test_load_tester_run():
    from load_test import LoadTester
    tester = LoadTester()

    def mock_func():
        time.sleep(0.001)
        return "ok"

    result = tester.run_load_test(
        test_name="Quick Test",
        func=mock_func,
        num_requests=10,
        concurrent_users=2
    )

    assert result.total_requests == 10
    assert result.successful_requests == 10
    assert result.failed_requests == 0
    assert result.error_rate == 0


def test_load_tester_with_errors():
    from load_test import LoadTester
    tester = LoadTester()

    call_count = 0
    def failing_func():
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            raise ValueError("Even calls fail")
        return "ok"

    result = tester.run_load_test(
        test_name="Error Test",
        func=failing_func,
        num_requests=10,
        concurrent_users=1
    )

    assert result.failed_requests > 0
    assert result.error_rate > 0


def test_load_tester_summary():
    from load_test import LoadTester
    tester = LoadTester()

    def mock_func():
        return "ok"

    tester.run_load_test("Test 1", mock_func, num_requests=5, concurrent_users=1)
    tester.run_load_test("Test 2", mock_func, num_requests=5, concurrent_users=1)

    summary = tester.get_summary()
    assert summary["total_tests"] == 2
    assert summary["total_requests"] == 10


def test_load_tester_print(capsys):
    from load_test import LoadTester
    tester = LoadTester()

    def mock_func():
        return "ok"

    result = tester.run_load_test("Print Test", mock_func, num_requests=5, concurrent_users=1)
    tester.print_results(result)

    captured = capsys.readouterr()
    assert "Print Test" in captured.out
    assert "Total Requests" in captured.out
