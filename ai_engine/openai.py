"""Drop-in replacement for openai.OpenAI — routes through AI Synapse core."""
from typing import Dict
import logging

from ._engine import get_engine, _resolve_config
from .resources.chat import Completions
from .resources.models import Models
from .resources.embeddings import Embeddings
from .resources.images import Images

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
        self._engine = get_engine(self._config)
        self._chat = _ChatNamespace(self._engine)
        self._models = Models(self._engine)
        self._embeddings = Embeddings(self._engine)
        self._images = Images(self._engine)

    @property
    def chat(self) -> _ChatNamespace:
        return self._chat

    @property
    def models(self) -> Models:
        return self._models

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    @property
    def images(self) -> Images:
        return self._images

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

    def serve(self, host: str = "0.0.0.0", port: int = 8000, **kwargs):
        """Start the AI Engine web server with dashboard, chat UI, and REST API.

        This starts a FastAPI server that provides:
        - OpenAI-compatible REST API at /v1/
        - Web dashboard at /
        - Chat UI at /chat
        - Swagger docs at /docs

        Args:
            host: Bind address (default: 0.0.0.0)
            port: Port number (default: 8000)
        """
        from core.config_sync import config_fetcher

        config_fetcher.initialize()

        from ai_engine.server.app import app
        import uvicorn

        uvicorn.run(app, host=host, port=port, **kwargs)


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
        from .resources.models import AsyncModels
        from .resources.embeddings import AsyncEmbeddings
        from .resources.images import AsyncImages
        self._config = _resolve_config(**kwargs)
        self._engine = get_engine(self._config)
        self._chat = _AsyncChatNamespace(self._engine)
        self._models = AsyncModels(self._engine)
        self._embeddings = AsyncEmbeddings(self._engine)
        self._images = AsyncImages(self._engine)

    @property
    def chat(self):
        return self._chat

    @property
    def models(self):
        return self._models

    @property
    def embeddings(self):
        return self._embeddings

    @property
    def images(self):
        return self._images


class _AsyncChatNamespace:
    """Async namespace for client.chat.*"""

    def __init__(self, engine):
        from .resources.chat import AsyncCompletions
        self._completions = AsyncCompletions(engine)

    @property
    def completions(self):
        return self._completions
