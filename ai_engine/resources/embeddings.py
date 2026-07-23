"""Embeddings resource — client.embeddings.create(...)"""
from __future__ import annotations

from typing import Optional, Sequence, Union

TextInput = Union[str, Sequence[str]]


class Embeddings:
    """OpenAI-compatible embeddings resource."""

    def __init__(self, engine=None):
        self._engine = engine

    def create(
        self,
        *,
        input: TextInput,
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        encoding_format: str = "float",
        user: Optional[str] = None,
        **kwargs,
    ):
        from core.embeddings import create_embeddings

        result = create_embeddings(
            input,
            model=model,
            dimensions=dimensions,
            encoding_format=encoding_format,
            prefer_remote=kwargs.get("prefer_remote", True),
            endpoint=kwargs.get("endpoint"),
            api_key=kwargs.get("api_key"),
        )
        return EmbeddingResponse(result)


class AsyncEmbeddings:
    """Async embeddings resource."""

    def __init__(self, engine=None):
        self._engine = engine

    async def create(
        self,
        *,
        input: TextInput,
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        encoding_format: str = "float",
        user: Optional[str] = None,
        **kwargs,
    ):
        import asyncio
        from core.embeddings import create_embeddings

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: create_embeddings(
                input,
                model=model,
                dimensions=dimensions,
                encoding_format=encoding_format,
                prefer_remote=kwargs.get("prefer_remote", True),
                endpoint=kwargs.get("endpoint"),
                api_key=kwargs.get("api_key"),
            ),
        )
        return EmbeddingResponse(result)


class EmbeddingResponse:
    """Minimal OpenAI-compatible embeddings response object."""

    def __init__(self, data: dict):
        self._data = data
        self.object = data.get("object", "list")
        self.model = data.get("model", "")
        self.data = [EmbeddingData(d) for d in data.get("data", [])]
        usage = data.get("usage") or {}
        self.usage = Usage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
        self.backend = data.get("backend")

    def model_dump(self) -> dict:
        return self._data

    def to_dict(self) -> dict:
        return self._data


class EmbeddingData:
    def __init__(self, d: dict):
        self.object = d.get("object", "embedding")
        self.embedding = d.get("embedding", [])
        self.index = d.get("index", 0)


class Usage:
    def __init__(self, prompt_tokens: int = 0, total_tokens: int = 0):
        self.prompt_tokens = prompt_tokens
        self.total_tokens = total_tokens
