"""Pydantic response types matching the OpenAI SDK format."""
from typing import Optional, List, Any, Dict
from dataclasses import dataclass, field
import time
import uuid


@dataclass
class Usage:
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatCompletionMessage:
    """Message in a chat completion."""
    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None
    function_call: Optional[Any] = None


@dataclass
class ChatCompletionChoice:
    """Single choice in a chat completion."""
    index: int = 0
    message: ChatCompletionMessage = field(default_factory=ChatCompletionMessage)
    finish_reason: Optional[str] = "stop"
    logprobs: Optional[Any] = None


@dataclass
class ChatCompletion:
    """Chat completion response — matches OpenAI SDK format."""
    id: str = ""
    object: str = "chat.completion"
    created: int = 0
    model: str = ""
    choices: List[ChatCompletionChoice] = field(default_factory=list)
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = None


@dataclass
class ChatCompletionChunkDelta:
    """Delta in a streaming chunk."""
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None


@dataclass
class ChatCompletionChunkChoice:
    """Single choice in a streaming chunk."""
    index: int = 0
    delta: ChatCompletionChunkDelta = field(default_factory=ChatCompletionChunkDelta)
    finish_reason: Optional[str] = None
    logprobs: Optional[Any] = None


@dataclass
class ChatCompletionChunk:
    """Streaming chunk — matches OpenAI SDK format."""
    id: str = ""
    object: str = "chat.completion.chunk"
    created: int = 0
    model: str = ""
    choices: List[ChatCompletionChunkChoice] = field(default_factory=list)
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = None


@dataclass
class Model:
    """Model info — matches OpenAI SDK format."""
    id: str = ""
    object: str = "model"
    created: int = 0
    owned_by: str = ""


@dataclass
class ModelList:
    """List of models — matches OpenAI SDK format."""
    object: str = "list"
    data: List[Model] = field(default_factory=list)


def _parse_chat_completion(data: Dict[str, Any]) -> ChatCompletion:
    """Parse a dict into a ChatCompletion object."""
    choices = []
    for c in data.get("choices", []):
        msg = c.get("message", {})
        choices.append(ChatCompletionChoice(
            index=c.get("index", 0),
            message=ChatCompletionMessage(
                role=msg.get("role", "assistant"),
                content=msg.get("content"),
                tool_calls=msg.get("tool_calls"),
                function_call=msg.get("function_call"),
            ),
            finish_reason=c.get("finish_reason"),
            logprobs=c.get("logprobs"),
        ))

    usage_data = data.get("usage")
    usage = None
    if usage_data:
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

    return ChatCompletion(
        id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:24]}"),
        object=data.get("object", "chat.completion"),
        created=data.get("created", int(time.time())),
        model=data.get("model", ""),
        choices=choices,
        usage=usage,
        system_fingerprint=data.get("system_fingerprint"),
    )


def _parse_chat_completion_chunk(data: Dict[str, Any]) -> ChatCompletionChunk:
    """Parse a dict into a ChatCompletionChunk object."""
    choices = []
    for c in data.get("choices", []):
        delta_data = c.get("delta", {})
        choices.append(ChatCompletionChunkChoice(
            index=c.get("index", 0),
            delta=ChatCompletionChunkDelta(
                role=delta_data.get("role"),
                content=delta_data.get("content"),
                tool_calls=delta_data.get("tool_calls"),
            ),
            finish_reason=c.get("finish_reason"),
            logprobs=c.get("logprobs"),
        ))

    return ChatCompletionChunk(
        id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:24]}"),
        object=data.get("object", "chat.completion.chunk"),
        created=data.get("created", int(time.time())),
        model=data.get("model", ""),
        choices=choices,
        usage=data.get("usage"),
        system_fingerprint=data.get("system_fingerprint"),
    )


def _parse_model(data: Dict[str, Any]) -> Model:
    """Parse a dict into a Model object."""
    return Model(
        id=data.get("id", ""),
        object=data.get("object", "model"),
        created=data.get("created", 0),
        owned_by=data.get("owned_by", ""),
    )


def _parse_model_list(data: Dict[str, Any]) -> ModelList:
    """Parse a dict into a ModelList object."""
    models = [_parse_model(m) for m in data.get("data", [])]
    return ModelList(
        object=data.get("object", "list"),
        data=models,
    )
