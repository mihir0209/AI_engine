"""Drop-in replacement for openai.OpenAI — routes through AI Engine core."""
from functools import cached_property
from typing import Dict, Any, Optional
import logging

from ._engine import get_engine, _resolve_config, _init_engine
from .resources.chat import Completions
from .resources.models import Models

logger = logging.getLogger("ai_engine")


class _ChatNamespace:
    """Namespace for client.chat.*"""

    def __init__(self, engine):
        self._completions = Completions(engine)

    @property
    def completions(self) -> Completions:
        return self._completions


class OpenAI:
    """Drop-in replacement for openai.OpenAI.

    Routes all requests through AI Engine's free multi-provider infrastructure.

    Usage:
        from ai_engine import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    def __init__(
        self,
        *,
        api_key: str = "dummy",
        base_url: str = None,
        config=None,
        cdn_config: str = None,
        timeout: int = 30,
        max_retries: int = 2,
        api_keys: Dict[str, str] = None,
        **kwargs,
    ):
        self._config = _resolve_config(
            config=config,
            cdn_config=cdn_config,
            api_keys=api_keys or {},
            timeout=timeout,
            max_retries=max_retries,
            **kwargs,
        )
        self._engine = _init_engine(self._config)
        self._chat = _ChatNamespace(self._engine)
        self._models = Models(self._engine)

    @property
    def chat(self) -> _ChatNamespace:
        return self._chat

    @property
    def models(self) -> Models:
        return self._models

    def config_status(self):
        """Get CDN config sync status."""
        try:
            from core.config_sync import config_fetcher
            return config_fetcher.get_status()
        except ImportError:
            return {"enabled": False}

    def refresh_config(self):
        """Force refresh CDN config."""
        try:
            from core.config_sync import config_fetcher, CACHE_META, CACHE_FILE
            CACHE_META.unlink(missing_ok=True)
            CACHE_FILE.unlink(missing_ok=True)
            config_fetcher.fetch_and_apply()
        except Exception as e:
            logger.warning(f"CDN refresh failed: {e}")

    def check_image_compatibility(self, provider: str, model: str = None):
        """Check if a provider/model supports image uploads."""
        from core.capabilities import capability_manager
        return capability_manager.check_image_compatibility(provider, model)


class AsyncOpenAI:
    """Async drop-in replacement for openai.AsyncOpenAI.

    Usage:
        from ai_engine import AsyncOpenAI

        async def main():
            client = AsyncOpenAI()
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello!"}]
            )
            print(response.choices[0].message.content)
    """

    def __init__(self, **kwargs):
        self._sync_client = OpenAI(**kwargs)

    @property
    def chat(self):
        return self._sync_client.chat

    @property
    def models(self):
        return self._sync_client.models
