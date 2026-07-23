"""Chat completions resource — wraps AI_engine.chat_completion()."""
import asyncio
import time
import uuid
from typing import List, Dict, Any, Optional


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

        preferred = kwargs.get("preferred_provider") or kwargs.get("provider")
        force = kwargs.get("force_provider", False)
        result = self._engine.chat_completion(
            messages=messages,
            model=model if model != "auto" else None,
            preferred_provider=preferred,
            force_provider=force,
        )

        if not result or not getattr(result, "success", False):
            from .._exceptions import InternalServerError
            error_msg = getattr(result, "error_message", "Unknown error") if result else "No response"
            raise InternalServerError(message=error_msg)

        def _message_text(message: Dict[str, Any]) -> str:
            content = message.get("content", "")
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(str(part.get("text") or ""))
                return " ".join(parts)
            return str(content or "")

        response_content = getattr(result, "content", None) or ""

        # Build OpenAI-compatible response
        prompt_tokens = sum(len(_message_text(m).split()) for m in messages)
        completion_tokens = len(response_content.split())

        return ChatCompletion(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            object="chat.completion",
            created=int(time.time()),
            model=result.model_used or model,
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=response_content,
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
        """Yield ChatCompletionChunk objects for streaming.

        Uses the engine's real SSE streaming when available, falls back to
        simulated word-by-word streaming.
        """
        from ..types import ChatCompletionChunk, ChatCompletionChunkChoice, ChatCompletionChunkDelta
        from .._exceptions import InternalServerError

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        preferred = kwargs.get("preferred_provider") or kwargs.get("provider")
        force = kwargs.get("force_provider", False)

        # Try real SSE streaming first
        if hasattr(self._engine, 'chat_completion_stream'):
            actual_model = model if model != "auto" else None
            chunk_count = 0
            try:
                for chunk in self._engine.chat_completion_stream(
                    messages=messages,
                    model=actual_model,
                    preferred_provider=preferred,
                    force_provider=force,
                ):
                    if chunk.get("error"):
                        raise InternalServerError(message=chunk["error"])
                    if chunk.get("done"):
                        break

                    content = chunk.get("content", "")
                    if content:
                        chunk_count += 1
                        yield ChatCompletionChunk(
                            id=completion_id,
                            object="chat.completion.chunk",
                            created=created,
                            model=actual_model or "auto",
                            choices=[ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(content=content),
                                finish_reason=None,
                            )],
                        )

                # If we got real chunks, emit the final chunk
                if chunk_count > 0:
                    yield ChatCompletionChunk(
                        id=completion_id,
                        object="chat.completion.chunk",
                        created=created,
                        model=actual_model or "auto",
                        choices=[ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(),
                            finish_reason="stop",
                        )],
                    )
                    return
            except Exception:
                pass  # Fall back to simulated streaming

        # Fallback: non-streaming request + word-by-word simulation
        result = self._engine.chat_completion(
            messages=messages,
            model=model if model != "auto" else None,
            preferred_provider=preferred,
            force_provider=force,
        )

        if not result or not getattr(result, "success", False):
            error_msg = getattr(result, "error_message", "Unknown error") if result else "No response"
            raise InternalServerError(message=error_msg)

        actual_model = result.model_used or model
        content = getattr(result, "content", None) or ""

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


class AsyncCompletions:
    """Async Chat.Completions resource — await client.chat.completions.create(...)"""

    def __init__(self, engine):
        self._engine = engine

    async def create(
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
        """Create a chat completion asynchronously.

        Returns ChatCompletion for non-streaming, or an async generator for streaming.
        """
        if stream:
            return self._stream(model, messages, temperature=temperature,
                              max_tokens=max_tokens, **kwargs)

        from ..types import ChatCompletion, ChatCompletionChoice, ChatCompletionMessage, Usage

        preferred = kwargs.get("preferred_provider") or kwargs.get("provider")
        force = kwargs.get("force_provider", False)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._engine.chat_completion(
                messages=messages,
                model=model if model != "auto" else None,
                preferred_provider=preferred,
                force_provider=force,
            ),
        )

        if not result or not getattr(result, "success", False):
            from .._exceptions import InternalServerError
            error_msg = getattr(result, "error_message", "Unknown error") if result else "No response"
            raise InternalServerError(message=error_msg)

        def _message_text(message: Dict[str, Any]) -> str:
            content = message.get("content", "")
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(str(part.get("text") or ""))
                return " ".join(parts)
            return str(content or "")

        response_content = getattr(result, "content", None) or ""

        prompt_tokens = sum(len(_message_text(m).split()) for m in messages)
        completion_tokens = len(response_content.split())

        return ChatCompletion(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            object="chat.completion",
            created=int(time.time()),
            model=result.model_used or model,
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=response_content,
                ),
                finish_reason="stop",
            )],
            usage=Usage(
                prompt_tokens=max(1, prompt_tokens),
                completion_tokens=max(1, completion_tokens),
                total_tokens=max(1, prompt_tokens + completion_tokens),
            ),
        )

    async def _stream(self, model, messages, temperature=None, max_tokens=None, **kwargs):
        """Async generator yielding ChatCompletionChunk objects for streaming."""
        from ..types import ChatCompletionChunk, ChatCompletionChunkChoice, ChatCompletionChunkDelta

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        preferred = kwargs.get("preferred_provider") or kwargs.get("provider")
        force = kwargs.get("force_provider", False)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._engine.chat_completion(
                messages=messages,
                model=model if model != "auto" else None,
                preferred_provider=preferred,
                force_provider=force,
            ),
        )

        if not result or not getattr(result, "success", False):
            from .._exceptions import InternalServerError
            error_msg = getattr(result, "error_message", "Unknown error") if result else "No response"
            raise InternalServerError(message=error_msg)

        actual_model = result.model_used or model
        content = getattr(result, "content", None) or ""

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
