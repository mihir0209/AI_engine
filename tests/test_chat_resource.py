"""Tests for OpenAI-compatible chat resource."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_engine.resources.chat import Completions


def test_create_handles_none_content():
    engine = MagicMock()
    engine.chat_completion.return_value = SimpleNamespace(
        success=True,
        content=None,
        model_used="test-model",
        provider_used="test-provider",
    )
    completions = Completions(engine)
    result = completions.create(
        model="test-model",
        messages=[{"role": "user", "content": "hello"}],
        stream=False,
    )
    assert result.choices[0].message.content == ""


def test_create_handles_multimodal_messages():
    engine = MagicMock()
    engine.chat_completion.return_value = SimpleNamespace(
        success=True,
        content="ok",
        model_used="vision-model",
        provider_used="gemini",
    )
    completions = Completions(engine)
    result = completions.create(
        model="vision-model",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "what is this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        }],
        stream=False,
    )
    assert result.choices[0].message.content == "ok"