"""Shared chat routing for TUI — same engine path as server chat and SDK."""

from __future__ import annotations

from typing import Any, Iterator

from core.ai_engine import AI_engine


def get_shared_engine() -> AI_engine:
    """Return a configured engine for TUI text and media requests."""
    return AI_engine(verbose=False)


def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    preferred_provider: str | None = None,
    force_provider: bool = False,
    **kwargs: Any,
):
    """Route through the canonical core engine contract."""
    return get_shared_engine().chat_completion(
        messages=messages,
        model=model,
        preferred_provider=preferred_provider,
        force_provider=force_provider,
        **kwargs,
    )


def stream_chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    preferred_provider: str | None = None,
    force_provider: bool = False,
    **kwargs: Any,
) -> Iterator[dict[str, Any]]:
    """Yield normalized chunks from the core engine's native stream contract."""
    yield from get_shared_engine().chat_completion_stream(
        messages=messages,
        model=model,
        preferred_provider=preferred_provider,
        force_provider=force_provider,
        **kwargs,
    )
