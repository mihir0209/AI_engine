"""Chat completions resource — wraps AI_engine.chat_completion()."""
import time
import uuid
from typing import List, Dict, Any, Optional, Iterator, Union


class Completions:
    """Chat.Completions resource — client.chat.completions.create(...)"""

    def __init__(self, engine):
        self._engine = engine

    def create(
        self,
        *,
        model: str = "auto",
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        n: int = 1,
        user: Optional[str] = None,
        **kwargs,
    ):
        """Create a chat completion.

        Returns ChatCompletion for non-streaming, or yields ChatCompletionChunk for streaming.
        """
        if stream:
            return self._stream(model, messages, temperature=temperature,
                              max_tokens=max_tokens, **kwargs)

        from ..types import ChatCompletion, ChatCompletionChoice, ChatCompletionMessage, Usage

        result = self._engine.chat_completion(
            messages=messages,
            model=model if model != "auto" else None,
            preferred_provider=kwargs.get("preferred_provider"),
            force_provider=kwargs.get("force_provider", False),
        )

        if not result or not getattr(result, "success", False):
            from .._exceptions import raise_for_status, InternalServerError
            error_msg = getattr(result, "error_message", "Unknown error") if result else "No response"
            raise InternalServerError(message=error_msg)

        # Build OpenAI-compatible response
        prompt_tokens = sum(len(m.get("content", "").split()) for m in messages)
        completion_tokens = len(result.content.split())

        return ChatCompletion(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            object="chat.completion",
            created=int(time.time()),
            model=result.model_used or model,
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=result.content,
                ),
                finish_reason="stop",
            )],
            usage=Usage(
                prompt_tokens=max(1, prompt_tokens),
                completion_tokens=max(1, completion_tokens),
                total_tokens=max(1, prompt_tokens + completion_tokens),
            ),
        )

    def _stream(self, model, messages, temperature=None, max_tokens=None, **kwargs):
        """Yield ChatCompletionChunk objects for streaming."""
        from ..types import ChatCompletionChunk, ChatCompletionChunkChoice, ChatCompletionChunkDelta

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        result = self._engine.chat_completion(
            messages=messages,
            model=model if model != "auto" else None,
            preferred_provider=kwargs.get("preferred_provider"),
            force_provider=kwargs.get("force_provider", False),
        )

        if not result or not getattr(result, "success", False):
            from .._exceptions import InternalServerError
            error_msg = getattr(result, "error_message", "Unknown error") if result else "No response"
            raise InternalServerError(message=error_msg)

        actual_model = result.model_used or model
        content = getattr(result, "content", "")

        # First chunk: role
        yield ChatCompletionChunk(
            id=completion_id,
            object="chat.completion.chunk",
            created=created,
            model=actual_model,
            choices=[ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(role="assistant", content=""),
                finish_reason=None,
            )],
        )

        # Content chunks (word by word)
        words = content.split(" ")
        for i, word in enumerate(words):
            chunk_content = (" " if i > 0 else "") + word + (" " if i < len(words) - 1 else "")
            yield ChatCompletionChunk(
                id=completion_id,
                object="chat.completion.chunk",
                created=created,
                model=actual_model,
                choices=[ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(content=chunk_content),
                    finish_reason=None,
                )],
            )

        # Final chunk
        yield ChatCompletionChunk(
            id=completion_id,
            object="chat.completion.chunk",
            created=created,
            model=actual_model,
            choices=[ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(),
                finish_reason="stop",
            )],
        )
