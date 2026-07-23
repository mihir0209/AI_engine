"""Multimodal OpenAI-compatible routes: embeddings, images, audio helpers.

Handlers are pure async functions taking body dicts so both dedicated
endpoints and /v1/uni can share them.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi.responses import JSONResponse


async def handle_embeddings(body: dict) -> Any:
    """OpenAI-compatible embeddings response (dict or JSONResponse on error)."""
    from core.embeddings import create_embeddings

    model = body.get("model", "text-embedding-3-small")
    input_text = body.get("input", "")

    if not input_text and input_text != 0:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "input is required", "type": "invalid_request_error"}},
        )

    dims = body.get("dimensions")
    encoding = body.get("encoding_format", "float")
    result = await asyncio.to_thread(
        create_embeddings,
        input_text,
        model=model,
        dimensions=dims,
        encoding_format=encoding,
    )
    result.pop("backend", None)
    return result


async def handle_image_generation(body: dict) -> Any:
    """OpenAI-compatible image generation response."""
    from core.image_generation import generate_image

    prompt = body.get("prompt", "")
    if not prompt:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "prompt is required", "type": "invalid_request_error"}},
        )

    result = await asyncio.to_thread(
        generate_image,
        prompt=prompt,
        model=body.get("model", "auto"),
        n=int(body.get("n", 1) or 1),
        size=body.get("size", "1024x1024"),
        response_format=body.get("response_format", "url"),
        provider=body.get("provider") or body.get("preferred_provider"),
    )
    if result.get("error") and not result.get("data"):
        code = 404 if "No image" in str(result.get("error")) else 500
        return JSONResponse(
            status_code=code,
            content={"error": {"message": result["error"], "type": "server_error"}},
        )
    return {"created": result.get("created", int(time.time())), "data": result.get("data", [])}
