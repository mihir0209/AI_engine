"""Shared chat routing for TUI — same engine path as server chat and SDK."""

from __future__ import annotations

from typing import Any

from core.ai_engine import AI_engine


def get_shared_engine() -> AI_engine:
    """Return a process-local engine instance (TUI / media helpers)."""
    return AI_engine(verbose=False)


def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    preferred_provider: str | None = None,
    force_provider: bool = False,
    **kwargs: Any,
):
    """Route through ``core.ai_engine`` — canonical with server and ``OpenAI`` SDK."""
    engine = get_shared_engine()
    return engine.chat_completion(
        messages=messages,
        model=model,
        preferred_provider=preferred_provider,
        force_provider=force_provider,
        **kwargs,
    )
