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


def _response(payload, status_code=200, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = payload
    return response


def test_azure_openai_success_posts_compatible_payload(engine):
    response = _response({"choices": [{"message": {"content": "azure answer"}}], "model": "deployment"})
    config = {"endpoint": "https://azure.example/chat", "max_tokens": 100, "temperature": 0.2, "timeout": 9}
    with patch.object(engine, "_get_current_api_key", return_value="azure-key"):
        with patch("requests.post", return_value=response) as post:
            result = engine._make_azure_openai_request(
                "azure", config, [{"role": "user", "content": "hello"}], model="deployment"
            )
    assert result.success and result.content == "azure answer"
    post.assert_called_once_with(
        config["endpoint"],
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 100,
            "temperature": 0.2,
            "stream": False,
            "model": "deployment",
        },
        headers={"Content-Type": "application/json", "Authorization": "Bearer azure-key"},
        timeout=9,
    )


def test_anthropic_maps_system_message_and_content(engine):
    response = _response({"content": [{"text": "anthropic answer"}], "model": "claude"})
    config = {"endpoint": "https://anthropic.example/messages", "max_tokens": 55, "timeout": 7}
    messages = [
        {"role": "system", "content": "Be concise"},
        {"role": "user", "content": "hello"},
    ]
    with patch.object(engine, "_get_current_api_key", return_value="anthropic-key"):
        with patch("requests.post", return_value=response) as post:
            result = engine._make_anthropic_request("anthropic", config, messages, model="claude")
    assert result.success and result.content == "anthropic answer"
    assert post.call_args.kwargs["headers"]["x-api-key"] == "anthropic-key"
    assert post.call_args.kwargs["json"] == {
        "model": "claude",
        "max_tokens": 55,
        "messages": [{"role": "user", "content": "hello"}],
        "system": "Be concise",
    }


def test_gemini_maps_roles_and_query_key(engine):
    response = _response({"candidates": [{"content": {"parts": [{"text": "gemini answer"}]}}]})
    config = {"endpoint": "https://gemini.example/generate", "max_tokens": 80, "temperature": 0.4}
    messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Question"},
        {"role": "assistant", "content": "Previous"},
    ]
    with patch.object(engine, "_get_current_api_key", return_value="gem-key"):
        with patch("requests.post", return_value=response) as post:
            result = engine._make_gemini_request("gemini", config, messages, model="gem-model")
    assert result.success and result.content == "gemini answer"
    assert post.call_args.args[0].endswith("?key=gem-key")
    assert post.call_args.kwargs["json"]["contents"] == [
        {"role": "user", "parts": [{"text": "Question"}]},
        {"role": "model", "parts": [{"text": "Previous"}]},
    ]


def test_cohere_maps_preamble_and_history(engine):
    response = _response({"message": {"content": [{"text": "cohere answer"}]}})
    messages = [
        {"role": "system", "content": "Preamble"},
        {"role": "user", "content": "Question"},
    ]
    with patch.object(engine, "_get_current_api_key", return_value="cohere-key"):
        with patch("requests.post", return_value=response) as post:
            result = engine._make_cohere_request("cohere", {"endpoint": "https://cohere.example"}, messages)
    assert result.success and result.content == "cohere answer"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer cohere-key"
    assert post.call_args.kwargs["json"]["preamble"] == "Preamble"
    assert post.call_args.kwargs["json"]["messages"] == [{"role": "user", "message": "Question"}]


def test_a3z_uses_get_and_quotes_user_message(engine):
    response = _response({}, text="a3z answer")
    with patch("requests.get", return_value=response) as get:
        result = engine._make_a3z_request(
            "a3z", {"endpoint": "https://a3z.example/chat", "timeout": 4},
            [{"role": "user", "content": "hello world"}], model="a3z-model"
        )
    assert result.success and result.content == "a3z answer"
    assert get.call_args.args[0] == "https://a3z.example/chat?message=hello%20world"
    assert get.call_args.kwargs["timeout"] == 4


def test_cloudflare_unwraps_result_response(engine):
    response = _response({"result": {"response": "cloudflare answer"}})
    config = {"endpoint": "https://cloudflare.example/run", "timeout": 8}
    with patch.object(engine, "_get_current_api_key", return_value="cf-key"):
        with patch("requests.post", return_value=response) as post:
            result = engine._make_cloudflare_request(
                "cloudflare", config, [{"role": "user", "content": "hello"}], model="cf-model"
            )
    assert result.success and result.content == "cloudflare answer"
    assert post.call_args.kwargs["json"] == {
        "messages": [{"role": "user", "content": "hello"}], "stream": False
    }


@pytest.mark.parametrize(
    "method, config",
    [
        ("_make_openai_request", {"endpoint": "https://example.com", "auth_type": "bearer"}),
        ("_make_anthropic_request", {"endpoint": "https://example.com"}),
        ("_make_gemini_request", {"endpoint": "https://example.com"}),
        ("_make_cohere_request", {"endpoint": "https://example.com"}),
        ("_make_cloudflare_request", {"endpoint": "https://example.com"}),
    ],
)
def test_provider_non_200_returns_typed_provider_error(engine, method, config):
    response = _response({}, status_code=429, text="rate limited")
    with patch.object(engine, "_get_current_api_key", return_value="key"):
        with patch("requests.post", return_value=response):
            result = getattr(engine, method)("provider", config, [{"role": "user", "content": "x"}])
    assert result.success is False
    assert result.error_type == "provider_error"
    assert result.status_code == 429


def test_ollama_streaming_parses_ndjson(engine):
    class FakeOllama:
        status_code = 200
        text = ""

        @staticmethod
        def iter_lines():
            yield b'{"response":"one","done":false}'
            yield b'{"response":"two","done":false}'
            yield b'{"done":true}'

    with patch("requests.post", return_value=FakeOllama()) as post:
        chunks = list(engine._make_ollama_streaming_request(
            "ollama", {"endpoint": "http://localhost:11434/api/generate", "timeout": 12},
            [{"role": "user", "content": "hello"}], model="llama"
        ))
    assert [chunk["content"] for chunk in chunks if "content" in chunk] == ["one", "two"]
    assert chunks[-1] == {"done": True}
    assert post.call_args.kwargs["json"] == {"model": "llama", "prompt": "hello", "stream": True}
