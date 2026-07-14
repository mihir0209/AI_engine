"""HTTP provider adapter tests (mocked requests)."""

from unittest.mock import MagicMock, patch

import pytest



@pytest.fixture
def engine(testing_engine):
    return testing_engine


def test_make_request_unknown_format_falls_back_to_openai(engine):
    config = {
        "format": "unknown_fmt",
        "endpoint": "https://example.com/v1/chat",
        "api_keys": ["k1"],
        "model": "m1",
        "timeout": 5,
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "hi"}}],
        "model": "m1",
    }
    with patch.object(engine, "_get_current_api_key", return_value="k1"):
        with patch("requests.post", return_value=mock_resp) as post:
            result = engine._make_request(
                "test_harness",
                config,
                [{"role": "user", "content": "hello"}],
                model="m1",
            )
    assert result.success is True
    assert result.content == "hi"
    post.assert_called_once()


def test_make_request_provider_exception_returns_typed_error(engine):
    config = {"format": "openai", "endpoint": "https://x", "api_keys": ["k"]}
    with patch.object(engine, "_make_openai_request", side_effect=RuntimeError("boom")):
        result = engine._make_request("p", config, [{"role": "user", "content": "x"}])
    assert result.success is False
    assert result.error_type == "provider_exception"
    assert "boom" in result.error_message


def test_azure_openai_no_api_key(engine):
    config = {"endpoint": "https://azure.example/openai", "api_keys": []}
    with patch.object(engine, "_get_current_api_key", return_value=None):
        result = engine._make_azure_openai_request(
            "azure",
            config,
            [{"role": "user", "content": "x"}],
        )
    assert result.success is False
    assert result.error_type == "auth_error"


def test_bedrock_not_implemented(engine):
    result = engine._make_bedrock_request(
        "bedrock",
        {},
        [{"role": "user", "content": "x"}],
    )
    assert result.success is False
    assert result.error_type == "not_implemented"


def test_streaming_request_yields_content(engine):
    config = {
        "endpoint": "https://example.com/stream",
        "api_keys": ["k"],
        "auth_type": "bearer",
        "model": "m",
        "timeout": 5,
    }

    class FakeIter:
        def __init__(self, lines):
            self._lines = lines

        def iter_lines(self):
            for line in self._lines:
                yield line

        status_code = 200
        text = ""

    fake = FakeIter(
        [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b"data: [DONE]",
        ]
    )
    with patch.object(engine, "_get_current_api_key", return_value="k"):
        with patch("requests.post", return_value=fake):
            chunks = list(
                engine._make_streaming_request(
                    "p",
                    config,
                    [{"role": "user", "content": "hi"}],
                )
            )
    assert any(c.get("content") == "Hello" for c in chunks)
    assert chunks[-1].get("done") is True
