"""Unit tests for Bedrock and Vertex AI request handlers."""
from unittest.mock import MagicMock, patch

import pytest

from core.ai_engine import AI_engine
from core.provider_requests import RequestResult


@pytest.fixture
def engine():
    eng = AI_engine(verbose=False)
    eng._get_current_api_key = MagicMock(return_value="AKIAtest:secretkey")
    return eng


class TestBedrockHandler:
    def test_no_api_key(self):
        eng = AI_engine(verbose=False)
        eng._get_current_api_key = MagicMock(return_value=None)
        result = eng._make_bedrock_request("bedrock", {}, [{"role": "user", "content": "hi"}])
        assert result.success is False
        assert result.error_type == "auth_error"

    def test_success_response(self, engine):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "output": {"message": {"content": [{"text": "Hello from Bedrock"}]}},
            "usage": {"inputTokens": 5, "outputTokens": 3},
        }
        config = {
            "endpoint": "https://bedrock-runtime.us-east-1.amazonaws.com",
            "model": "anthropic.claude-3-haiku-20240307-v1:0",
            "region": "us-east-1",
            "timeout": 30,
        }
        with patch("requests.post", return_value=mock_resp):
            result = engine._make_bedrock_request(
                "bedrock", config, [{"role": "user", "content": "hi"}]
            )
        assert result.success is True
        assert "Hello from Bedrock" in result.content
        assert result.provider_used == "bedrock"

    def test_http_error(self, engine):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Access Denied"
        config = {
            "endpoint": "https://bedrock-runtime.us-east-1.amazonaws.com",
            "model": "anthropic.claude-3-haiku-20240307-v1:0",
            "region": "us-east-1",
        }
        with patch("requests.post", return_value=mock_resp):
            result = engine._make_bedrock_request(
                "bedrock", config, [{"role": "user", "content": "hi"}]
            )
        assert result.success is False
        assert result.error_type == "provider_error"
        assert result.status_code == 403

    def test_system_prompt_conversion(self, engine):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "output": {"message": {"content": [{"text": "ok"}]}},
        }
        config = {
            "endpoint": "https://bedrock-runtime.us-east-1.amazonaws.com",
            "model": "anthropic.claude-3-haiku-20240307-v1:0",
            "region": "us-east-1",
        }
        messages = [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "hi"},
        ]
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = engine._make_bedrock_request("bedrock", config, messages)
        assert result.success is True
        # Ensure POST was called with system block in payload
        call_kwargs = mock_post.call_args
        assert call_kwargs is not None


class TestVertexAIHandler:
    def test_no_api_key(self):
        eng = AI_engine(verbose=False)
        eng._get_current_api_key = MagicMock(return_value=None)
        result = eng._make_vertex_ai_request(
            "vertex", {"project_id": "p", "region": "us-central1"},
            [{"role": "user", "content": "hi"}],
        )
        assert result.success is False
        assert result.error_type == "auth_error"

    def test_success_response(self, engine):
        engine._get_current_api_key = MagicMock(return_value="ya29.token")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "Hello from Vertex"}]}}
            ],
            "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 4},
        }
        config = {
            "project_id": "my-project",
            "region": "us-central1",
            "model": "gemini-1.5-pro",
            "timeout": 30,
        }
        with patch("requests.post", return_value=mock_resp):
            result = engine._make_vertex_ai_request(
                "vertex", config, [{"role": "user", "content": "hi"}]
            )
        assert result.success is True
        assert "Hello from Vertex" in result.content

    def test_http_error(self, engine):
        engine._get_current_api_key = MagicMock(return_value="ya29.token")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        config = {
            "project_id": "my-project",
            "region": "us-central1",
            "model": "gemini-1.5-pro",
        }
        with patch("requests.post", return_value=mock_resp):
            result = engine._make_vertex_ai_request(
                "vertex", config, [{"role": "user", "content": "hi"}]
            )
        assert result.success is False
        assert result.error_type == "provider_error"


class TestHttpClient:
    def test_post_json(self):
        from core.http_client import post_json
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            post_json("https://example.com", json_body={"a": 1}, timeout=5)
            mock_post.assert_called_once()

    def test_stream_sse(self):
        from core.http_client import stream_sse
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = [
            b"data: {\"c\":1}",
            b"",
            b"data: [DONE]",
        ]
        with patch("requests.post", return_value=mock_resp):
            lines = list(stream_sse("https://example.com", json_body={}))
        assert lines == ['{"c":1}', "[DONE]"]
