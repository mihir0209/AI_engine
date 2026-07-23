"""Tests for embeddings module and SDK resource."""
import math

import pytest

from core.embeddings import (
    create_embeddings,
    local_embedding,
    local_embeddings,
    remote_embeddings,
)


class TestLocalEmbeddings:
    def test_dimensions(self):
        v = local_embedding("hello world", dimensions=64)
        assert len(v) == 64
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-6

    def test_deterministic(self):
        a = local_embedding("same text", dimensions=32)
        b = local_embedding("same text", dimensions=32)
        assert a == b

    def test_different_texts_differ(self):
        a = local_embedding("alpha", dimensions=32)
        b = local_embedding("beta", dimensions=32)
        assert a != b

    def test_batch(self):
        vecs = local_embeddings(["a", "b"], dimensions=16)
        assert len(vecs) == 2
        assert len(vecs[0]) == 16


class TestCreateEmbeddings:
    def test_local_fallback(self):
        result = create_embeddings("hi there", model="text-embedding-3-small", prefer_remote=False, dimensions=128)
        assert result["object"] == "list"
        assert len(result["data"]) == 1
        assert len(result["data"][0]["embedding"]) == 128
        assert result["backend"] == "local"
        assert result["usage"]["prompt_tokens"] >= 1

    def test_list_input(self):
        result = create_embeddings(["one", "two"], prefer_remote=False, dimensions=32)
        assert len(result["data"]) == 2
        assert result["data"][0]["index"] == 0
        assert result["data"][1]["index"] == 1

    def test_base64_encoding(self):
        result = create_embeddings("x", prefer_remote=False, dimensions=8, encoding_format="base64")
        emb = result["data"][0]["embedding"]
        assert isinstance(emb, str)
        assert len(emb) > 0

    def test_remote_none_without_config(self, monkeypatch):
        monkeypatch.delenv("EMBEDDINGS_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("EMBEDDINGS_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert remote_embeddings("hi") is None


class TestSDKEmbeddings:
    def test_sync_create(self):
        from ai_engine.resources.embeddings import Embeddings

        client = Embeddings()
        resp = client.create(input="hello", prefer_remote=False, dimensions=64)
        assert len(resp.data) == 1
        assert len(resp.data[0].embedding) == 64
        assert resp.usage.total_tokens >= 1

    @pytest.mark.asyncio
    async def test_async_create(self):
        from ai_engine.resources.embeddings import AsyncEmbeddings

        client = AsyncEmbeddings()
        resp = await client.create(input=["a", "b"], prefer_remote=False, dimensions=32)
        assert len(resp.data) == 2


class TestOpenAIClientSurface:
    def test_openai_has_embeddings_and_images(self):
        from ai_engine import OpenAI

        # Don't init full engine path if heavy — just check class attributes after mock-free import
        assert hasattr(OpenAI, "__init__")
        # Instantiate may load config; use testing mode env
        import os
        os.environ.setdefault("AI_ENGINE_MODE", "testing")
        client = OpenAI()
        assert hasattr(client, "embeddings")
        assert hasattr(client, "images")
        r = client.embeddings.create(input="test", prefer_remote=False, dimensions=16)
        assert len(r.data[0].embedding) == 16
