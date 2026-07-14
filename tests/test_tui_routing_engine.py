"""Tests for the TUI-to-core routing contract."""

from types import SimpleNamespace
from unittest.mock import patch

from ai_engine.tui import routing_engine


def test_chat_completion_forwards_core_contract():
    result = SimpleNamespace(success=True, content="answer")
    fake_engine = SimpleNamespace(chat_completion=lambda **kwargs: result)
    with patch.object(routing_engine, "get_shared_engine", return_value=fake_engine):
        actual = routing_engine.chat_completion(
            [{"role": "user", "content": "hello"}],
            model="provider/model",
            preferred_provider="provider",
            force_provider=True,
            temperature=0.2,
        )
    assert actual is result


def test_stream_chat_completion_preserves_native_chunks():
    chunks = [
        {"content": "hello"},
        {"content": " world"},
        {"done": True, "provider": "p", "model": "m"},
    ]
    fake_engine = SimpleNamespace(chat_completion_stream=lambda **kwargs: iter(chunks))
    with patch.object(routing_engine, "get_shared_engine", return_value=fake_engine):
        actual = list(routing_engine.stream_chat_completion(
            [{"role": "user", "content": "hello"}], model="m"
        ))
    assert actual == chunks


def test_stream_chat_completion_preserves_error_chunk():
    error = {"error": "provider failed", "done": True}
    fake_engine = SimpleNamespace(chat_completion_stream=lambda **kwargs: iter([error]))
    with patch.object(routing_engine, "get_shared_engine", return_value=fake_engine):
        assert list(routing_engine.stream_chat_completion([])) == [error]
