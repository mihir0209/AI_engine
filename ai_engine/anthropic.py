"""Anthropic SDK compatibility — placeholder for future implementation."""
from ._engine import get_engine


class Anthropic:
    """Drop-in replacement for anthropic.Anthropic (future implementation).

    Usage:
        from ai_engine import Anthropic
        client = Anthropic(api_key="dummy")
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    def __init__(self, *, api_key: str = "dummy", **kwargs):
        self._api_key = api_key
        raise NotImplementedError(
            "Anthropic compatibility is coming in a future release. "
            "Use OpenAI compatibility instead: from ai_engine import OpenAI"
        )


class AsyncAnthropic:
    """Async Anthropic placeholder (future implementation)."""

    def __init__(self, **kwargs):
        raise NotImplementedError(
            "AsyncAnthropic compatibility is coming in a future release. "
            "Use AsyncOpenAI instead: from ai_engine import AsyncOpenAI"
        )
