"""Images resource — client.images.generate(...)"""
from __future__ import annotations

import asyncio


class Images:
    """OpenAI-compatible images resource."""

    def __init__(self, engine):
        self._engine = engine

    def generate(
        self,
        *,
        prompt: str,
        model: str = "auto",
        n: int = 1,
        size: str = "1024x1024",
        response_format: str = "url",
        quality: str = "standard",
        style: str = "vivid",
        **kwargs,
    ):
        from core.image_generation import generate_image

        return generate_image(
            prompt=prompt,
            model=model,
            n=n,
            size=size,
            response_format=response_format,
            engine=self._engine,
            provider=kwargs.get("provider") or kwargs.get("preferred_provider"),
        )


class AsyncImages:
    def __init__(self, engine):
        self._engine = engine

    async def generate(self, **kwargs):
        loop = asyncio.get_running_loop()
        images = Images(self._engine)
        return await loop.run_in_executor(None, lambda: images.generate(**kwargs))
