"""Anthropic SDK compatibility — routes Anthropic-style requests through AI Synapse core."""
from typing import List, Dict, Any, Optional, Union
import uuid


class AnthropicError(Exception):
    pass


class _MessagesResource:
    """client.messages resource."""

    def __init__(self, engine):
        self._engine = engine

    def create(
        self,
        *,
        model: str,
        max_tokens: int = 1024,
        messages: List[Dict[str, Any]],
        system: Optional[Union[str, List[Dict[str, Any]]]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        stream: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Create a message — Anthropic API compatible.

        Converts Anthropic messages format to OpenAI format internally,
        then routes through AI Engine's multi-provider infrastructure.
        """
        oai_messages = self._convert_messages(messages, system)

        if stream:
            return self._stream(model, oai_messages, max_tokens=max_tokens,
                               temperature=temperature, **kwargs)

        result = self._engine.chat_completion(
            messages=oai_messages,
            model=model,
        )

        if not result or not getattr(result, "success", False):
            error_msg = getattr(result, "error_message", "Unknown error") if result else "No response"
            raise AnthropicError(error_msg)

        content = getattr(result, "content", None) or ""

        return Message(
            id=f"msg_{uuid.uuid4().hex[:24]}",
            type="message",
            role="assistant",
            content=[TextBlock(type="text", text=content)],
            model=result.model_used or model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=max(1, sum(len(m.get("content", "").split()) for m in messages)),
                        output_tokens=max(1, len(content.split()))),
        )

    def _convert_messages(self, messages: List[Dict[str, Any]], system=None) -> List[Dict[str, str]]:
        """Convert Anthropic message format to OpenAI format."""
        oai_messages = []

        if system:
            if isinstance(system, str):
                oai_messages.append({"role": "system", "content": system})
            elif isinstance(system, list):
                text_parts = [b.get("text", "") for b in system if b.get("type") == "text"]
                oai_messages.append({"role": "system", "content": " ".join(text_parts)})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, str):
                oai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "image":
                            text_parts.append("[image]")
                oai_messages.append({"role": role, "content": " ".join(text_parts) if text_parts else str(content)})
            else:
                oai_messages.append({"role": role, "content": str(content)})

        return oai_messages

    def _stream(self, model, messages, max_tokens=1024, temperature=None, **kwargs):
        """Stream message chunks."""
        result = self._engine.chat_completion(messages=messages, model=model)

        if not result or not getattr(result, "success", False):
            error_msg = getattr(result, "error_message", "Unknown error") if result else "No response"
            raise AnthropicError(error_msg)

        content = getattr(result, "content", None) or ""
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"

        yield MessageStart(type="message_start", message=Message(
            id=msg_id, type="message", role="assistant", content=[],
            model=result.model_used or model, stop_reason=None,
            usage=Usage(input_tokens=0, output_tokens=0),
        ))

        words = content.split(" ")
        for i, word in enumerate(words):
            text = (" " if i > 0 else "") + word
            yield ContentBlockStart(type="content_block_start", index=0,
                                   content_block=TextBlock(type="text", text=""))
            yield ContentBlockDelta(type="content_block_delta", index=0,
                                   delta=TextDelta(type="text_delta", text=text))

        yield ContentBlockStop(type="content_block_stop", index=0)
        yield MessageDelta(type="message_delta", delta=StopDelta(stop_reason="end_turn"),
                          usage=Usage(output_tokens=max(1, len(words))))
        yield MessageStop(type="message_stop")


class Anthropic:
    """Drop-in replacement for anthropic.Anthropic.

    Routes all requests through AI Synapse's free multi-provider infrastructure.

    Usage:
        from ai_engine import Anthropic

        client = Anthropic()
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.content[0].text)
    """

    def __init__(self, *, api_key: str = "dummy", **kwargs):
        self._api_key = api_key
        from ._engine import get_engine, _resolve_config
        self._config = _resolve_config(**kwargs)
        self._engine = get_engine(self._config)
        self._messages = _MessagesResource(self._engine)

    @property
    def messages(self) -> _MessagesResource:
        return self._messages


class AsyncAnthropic:
    """Async drop-in replacement for anthropic.AsyncAnthropic.

    Usage:
        from ai_engine import AsyncAnthropic

        async def main():
            client = AsyncAnthropic()
            response = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello!"}]
            )
            print(response.content[0].text)
    """

    def __init__(self, **kwargs):
        self._sync_client = Anthropic(**kwargs)

    @property
    def messages(self):
        return self._sync_client.messages


class Message:
    def __init__(self, id, type, role, content, model, stop_reason, usage):
        self.id = id
        self.type = type
        self.role = role
        self.content = content
        self.model = model
        self.stop_reason = stop_reason
        self.usage = usage


class TextBlock:
    def __init__(self, type, text):
        self.type = type
        self.text = text


class Usage:
    def __init__(self, input_tokens=0, output_tokens=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class MessageStart:
    def __init__(self, type, message):
        self.type = type
        self.message = message


class ContentBlockStart:
    def __init__(self, type, index, content_block):
        self.type = type
        self.index = index
        self.content_block = content_block


class ContentBlockDelta:
    def __init__(self, type, index, delta):
        self.type = type
        self.index = index
        self.delta = delta


class ContentBlockStop:
    def __init__(self, type, index):
        self.type = type
        self.index = index


class MessageDelta:
    def __init__(self, type, delta, usage):
        self.type = type
        self.delta = delta
        self.usage = usage


class MessageStop:
    def __init__(self, type):
        self.type = type


class TextDelta:
    def __init__(self, type, text):
        self.type = type
        self.text = text


class StopDelta:
    def __init__(self, stop_reason):
        self.stop_reason = stop_reason
