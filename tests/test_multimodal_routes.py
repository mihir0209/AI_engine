"""Tests for multimodal route handlers."""
import pytest
from fastapi.responses import JSONResponse


@pytest.mark.asyncio
async def test_handle_embeddings_ok():
    from ai_engine.server.routes.multimodal import handle_embeddings

    resp = await handle_embeddings({"input": "hello", "dimensions": 32, "model": "local"})
    assert isinstance(resp, dict)
    assert len(resp["data"][0]["embedding"]) == 32


@pytest.mark.asyncio
async def test_handle_embeddings_missing_input():
    from ai_engine.server.routes.multimodal import handle_embeddings

    resp = await handle_embeddings({})
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_handle_image_missing_prompt():
    from ai_engine.server.routes.multimodal import handle_image_generation

    resp = await handle_image_generation({})
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 400
