"""Tests for ai_engine/anthropic.py — Anthropic SDK adapter."""
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass


@dataclass
class MockResult:
    success: bool
    content: str = ""
    model_used: str = ""
    error_message: str = ""
    error_type: str = ""


@pytest.fixture
def mock_engine():
    """Create a mock AI_engine instance."""
    engine = MagicMock()
    engine.chat_completion = MagicMock()
    return engine


class TestAnthropicSDK:
    def test_messages_create_success(self, mock_engine):
        """Test successful message creation."""
        mock_engine.chat_completion.return_value = MockResult(
            success=True,
            content="Hello! I'm Claude.",
            model_used="claude-3-haiku-20240307",
        )

        from ai_engine.anthropic import Anthropic, _MessagesResource

        client = Anthropic.__new__(Anthropic)
        client._messages = _MessagesResource(mock_engine)

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello!"}],
        )

        assert response is not None
        assert response.role == "assistant"
        assert response.model == "claude-3-haiku-20240307"
        assert len(response.content) == 1
        assert response.content[0].text == "Hello! I'm Claude."
        assert response.stop_reason == "end_turn"

    def test_messages_create_with_system_prompt(self, mock_engine):
        """Test message creation with system prompt."""
        mock_engine.chat_completion.return_value = MockResult(
            success=True,
            content="I'm a helpful assistant.",
            model_used="claude-3-haiku-20240307",
        )

        from ai_engine.anthropic import Anthropic, _MessagesResource

        client = Anthropic.__new__(Anthropic)
        client._messages = _MessagesResource(mock_engine)

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello!"}],
        )

        assert response is not None
        # Verify system message was included in the conversion
        call_args = mock_engine.chat_completion.call_args
        messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
        assert any(m.get("role") == "system" for m in messages)

    def test_messages_create_with_system_blocks(self, mock_engine):
        """Test message creation with system as content blocks."""
        mock_engine.chat_completion.return_value = MockResult(
            success=True,
            content="I'm a helpful assistant.",
            model_used="claude-3-haiku-20240307",
        )

        from ai_engine.anthropic import Anthropic, _MessagesResource

        client = Anthropic.__new__(Anthropic)
        client._messages = _MessagesResource(mock_engine)

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            system=[{"type": "text", "text": "You are helpful."}],
            messages=[{"role": "user", "content": "Hello!"}],
        )

        assert response is not None

    def test_messages_create_failure(self, mock_engine):
        """Test message creation when engine fails."""
        mock_engine.chat_completion.return_value = MockResult(
            success=False,
            error_message="Provider unavailable",
            error_type="provider_error",
        )

        from ai_engine.anthropic import Anthropic, AnthropicError, _MessagesResource

        client = Anthropic.__new__(Anthropic)
        client._messages = _MessagesResource(mock_engine)

        with pytest.raises(AnthropicError, match="Provider unavailable"):
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello!"}],
            )

    def test_messages_create_no_result(self, mock_engine):
        """Test message creation when engine returns None."""
        mock_engine.chat_completion.return_value = None

        from ai_engine.anthropic import Anthropic, AnthropicError, _MessagesResource

        client = Anthropic.__new__(Anthropic)
        client._messages = _MessagesResource(mock_engine)

        with pytest.raises(AnthropicError, match="No response"):
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello!"}],
            )

    def test_convert_messages_string_content(self, mock_engine):
        """Test message conversion with string content."""
        from ai_engine.anthropic import _MessagesResource

        resource = _MessagesResource(mock_engine)
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = resource._convert_messages(messages)

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello!"}
        assert result[1] == {"role": "assistant", "content": "Hi there!"}

    def test_convert_messages_list_content(self, mock_engine):
        """Test message conversion with list content (text blocks)."""
        from ai_engine.anthropic import _MessagesResource

        resource = _MessagesResource(mock_engine)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image", "source": {"type": "base64", "data": "..."}},
                ],
            },
        ]

        result = resource._convert_messages(messages)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert "What's in this image?" in result[0]["content"]
        assert "[image]" in result[0]["content"]

    def test_convert_messages_system_string(self, mock_engine):
        """Test message conversion with system as string."""
        from ai_engine.anthropic import _MessagesResource

        resource = _MessagesResource(mock_engine)
        messages = [{"role": "user", "content": "Hello!"}]

        result = resource._convert_messages(messages, system="Be helpful.")

        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "Be helpful."}
        assert result[1]["role"] == "user"

    def test_convert_messages_system_blocks(self, mock_engine):
        """Test message conversion with system as content blocks."""
        from ai_engine.anthropic import _MessagesResource

        resource = _MessagesResource(mock_engine)
        messages = [{"role": "user", "content": "Hello!"}]
        system = [
            {"type": "text", "text": "You are helpful."},
            {"type": "text", "text": "Be concise."},
        ]

        result = resource._convert_messages(messages, system=system)

        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert "You are helpful." in result[0]["content"]
        assert "Be concise." in result[0]["content"]

    def test_stream_yields_events(self, mock_engine):
        """Test that streaming yields proper Anthropic events."""
        mock_engine.chat_completion.return_value = MockResult(
            success=True,
            content="Hello world",
            model_used="claude-3-haiku-20240307",
        )

        from ai_engine.anthropic import _MessagesResource

        resource = _MessagesResource(mock_engine)
        events = list(resource._stream(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hi"}],
        ))

        # Should have: MessageStart, ContentBlockStart, ContentBlockDelta (x2 words),
        # ContentBlockStop, MessageDelta, MessageStop
        assert len(events) >= 6

        # First event should be MessageStart
        assert events[0].type == "message_start"
        assert events[0].message.role == "assistant"

        # Last event should be MessageStop
        assert events[-1].type == "message_stop"

    def test_stream_failure_raises_error(self, mock_engine):
        """Test that streaming raises error on failure."""
        mock_engine.chat_completion.return_value = MockResult(
            success=False,
            error_message="Provider error",
        )

        from ai_engine.anthropic import _MessagesResource, AnthropicError

        resource = _MessagesResource(mock_engine)

        with pytest.raises(AnthropicError, match="Provider error"):
            list(resource._stream(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hi"}],
            ))


class TestAsyncAnthropicSDK:
    @pytest.mark.asyncio
    async def test_async_messages_create_success(self, mock_engine):
        """Test async message creation."""
        mock_engine.chat_completion.return_value = MockResult(
            success=True,
            content="Hello! I'm Claude.",
            model_used="claude-3-haiku-20240307",
        )

        from ai_engine.anthropic import AsyncAnthropic, AsyncMessagesResource

        client = AsyncAnthropic.__new__(AsyncAnthropic)
        client._messages = AsyncMessagesResource(mock_engine)

        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello!"}],
        )

        assert response is not None
        assert response.role == "assistant"
        assert response.content[0].text == "Hello! I'm Claude."

    @pytest.mark.asyncio
    async def test_async_messages_create_failure(self, mock_engine):
        """Test async message creation failure."""
        mock_engine.chat_completion.return_value = MockResult(
            success=False,
            error_message="Async error",
        )

        from ai_engine.anthropic import AsyncAnthropic, AsyncMessagesResource, AnthropicError

        client = AsyncAnthropic.__new__(AsyncAnthropic)
        client._messages = AsyncMessagesResource(mock_engine)

        with pytest.raises(AnthropicError, match="Async error"):
            await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello!"}],
            )


class TestAnthropicDataClasses:
    def test_message_attributes(self):
        """Test Message dataclass has correct attributes."""
        from ai_engine.anthropic import Message, TextBlock, Usage

        msg = Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[TextBlock(type="text", text="Hello")],
            model="claude-3-haiku-20240307",
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=5),
        )

        assert msg.id == "msg_123"
        assert msg.type == "message"
        assert msg.role == "assistant"
        assert len(msg.content) == 1
        assert msg.content[0].text == "Hello"
        assert msg.model == "claude-3-haiku-20240307"
        assert msg.stop_reason == "end_turn"
        assert msg.usage.input_tokens == 10
        assert msg.usage.output_tokens == 5

    def test_streaming_event_classes(self):
        """Test streaming event classes exist and have correct attributes."""
        from ai_engine.anthropic import (
            MessageStart, ContentBlockStart, ContentBlockDelta,
            ContentBlockStop, MessageDelta, MessageStop,
            TextDelta, StopDelta, TextBlock,
        )

        msg = MagicMock()
        assert MessageStart(type="message_start", message=msg).type == "message_start"

        block = TextBlock(type="text", text="")
        assert ContentBlockStart(type="content_block_start", index=0, content_block=block).index == 0

        delta = TextDelta(type="text_delta", text="hi")
        assert ContentBlockDelta(type="content_block_delta", index=0, delta=delta).delta.text == "hi"

        assert ContentBlockStop(type="content_block_stop", index=0).index == 0

        usage = MagicMock()
        stop_delta = StopDelta(stop_reason="end_turn")
        assert MessageDelta(type="message_delta", delta=stop_delta, usage=usage).delta.stop_reason == "end_turn"

        assert MessageStop(type="message_stop").type == "message_stop"
