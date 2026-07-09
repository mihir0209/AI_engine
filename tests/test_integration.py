"""
Integration tests with mocked providers
Tests the full request flow without actual API calls
"""
import pytest
from typing import Dict, List


class MockProvider:
    """Mock AI provider for testing"""

    def __init__(self, name: str, responses: List[Dict] = None, fail: bool = False):
        self.name = name
        self.responses = responses or [{"choices": [{"message": {"content": "Mock response"}}]}]
        self.fail = fail
        self.call_count = 0
        self.last_request = None

    def __call__(self, **kwargs):
        self.call_count += 1
        self.last_request = kwargs

        if self.fail:
            raise Exception(f"Mock {self.name} failure")

        return self.responses[self.call_count - 1 % len(self.responses)]


@pytest.fixture
def mock_providers():
    """Set of mock providers for testing"""
    return {
        "openai": MockProvider("openai"),
        "anthropic": MockProvider("anthropic"),
        "failing": MockProvider("failing", fail=True)
    }


class TestAIEngineIntegration:
    """Integration tests for AI Engine"""

    def test_engine_initialization(self):
        from core.ai_engine import AI_engine
        engine = AI_engine(verbose=False)
        assert len(engine.providers) > 0

    def test_provider_selection(self):
        from core.ai_engine import AI_engine
        engine = AI_engine(verbose=False)

        providers = engine._get_available_providers()
        assert len(providers) > 0

    def test_error_classification(self):
        from core.ai_engine import AI_engine
        engine = AI_engine(verbose=False)

        assert engine._classify_error("rate limit", 429) == "rate_limit"
        assert engine._classify_error("unauthorized", 401) == "auth_error"
        assert engine._classify_error("internal error", 500) == "server_error"

    def test_chat_completion_no_providers(self):
        from core.ai_engine import AI_engine
        engine = AI_engine(verbose=False)
        engine.providers = {}

        result = engine.chat_completion([{"role": "user", "content": "hi"}])
        assert result.success is False

    def test_model_matching(self):
        from core.ai_engine import AI_engine
        engine = AI_engine(verbose=False)

        assert engine.model_matches("gpt-4", "gpt-4") is True
        assert engine.model_matches("gpt-4", "gpt-4-turbo") is True
        assert engine.model_matches("gpt-4", "claude-3") is False


class TestRouterIntegration:
    """Integration tests for chat router"""

    def test_chat_lifecycle(self, server_client):
        """Test full chat lifecycle: create, message, edit, delete"""
        # Create
        create_resp = server_client.post("/api/chat/chats", json={"title": "Integration Test"})
        assert create_resp.status_code == 200
        chat_id = create_resp.json()["chat_id"]

        # Get
        get_resp = server_client.get(f"/api/chat/chats/{chat_id}")
        assert get_resp.status_code == 200

        # Update
        update_resp = server_client.put(f"/api/chat/chats/{chat_id}", json={"title": "Updated Title"})
        assert update_resp.status_code == 200

        # Add messages
        msg_resp = server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
            "role": "user", "content": "Hello"
        })
        assert msg_resp.status_code == 200

        # Search
        search_resp = server_client.post("/api/chat/search", json={"query": "Hello"})
        assert search_resp.status_code == 200

        # Export
        export_resp = server_client.get(f"/api/chat/chats/{chat_id}/export")
        assert export_resp.status_code == 200

        # Delete
        delete_resp = server_client.delete(f"/api/chat/chats/{chat_id}")
        assert delete_resp.status_code == 200

    def test_branching_workflow(self, server_client):
        """Test branching: create messages, branch, switch"""
        create_resp = server_client.post("/api/chat/chats", json={"title": "Branch Test"})
        chat_id = create_resp.json()["chat_id"]

        # Add messages
        msg1 = server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
            "role": "user", "content": "Message 1"
        }).json()["message_id"]

        server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
            "role": "system", "content": "Response 1"
        })

        msg3 = server_client.post(f"/api/chat/chats/{chat_id}/messages", json={
            "role": "user", "content": "Message 3"
        }).json()["message_id"]

        # Create branch
        branch_resp = server_client.post(f"/api/chat/chats/{chat_id}/branch/{msg3}")
        assert branch_resp.status_code == 200
        branch_id = branch_resp.json()["branch_id"]

        # Get branches
        branches_resp = server_client.get(f"/api/chat/chats/{chat_id}/branches")
        assert branches_resp.status_code == 200
        assert len(branches_resp.json()["branches"]) >= 1

        # Switch branch
        switch_resp = server_client.post(f"/api/chat/chats/{chat_id}/branches/{branch_id}/switch")
        assert switch_resp.status_code == 200


# Server endpoint coverage moved to tests/features/test_server_*.py



