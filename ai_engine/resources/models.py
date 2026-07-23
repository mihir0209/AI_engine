"""Models resource — wraps AI_engine model discovery with auto-population."""
import asyncio
import time
import logging

logger = logging.getLogger("ai_engine")


class Models:
    """Models resource — client.models.list(), client.models.retrieve()"""

    def __init__(self, engine):
        self._engine = engine

    def list(self, **kwargs):
        """List all available models.

        On first call, triggers model discovery from all enabled providers.
        Subsequent calls use the cached results.
        """
        from ..types import ModelList, Model

        try:
            from core.model_cache import shared_model_cache

            # If cache is empty, trigger discovery
            if not shared_model_cache.is_cache_valid():
                try:
                    self._engine._discover_and_cache_models_sync()
                except Exception as e:
                    logger.warning(f"Model discovery failed: {e}")

            # Now read from cache
            if shared_model_cache.is_cache_valid():
                model_ids = shared_model_cache.get_models()
            else:
                model_ids = []
        except ImportError:
            model_ids = []

        models = []
        for model_id in model_ids:
            # Models come in "provider|model" format from discovery
            if "|" in model_id:
                parts = model_id.split("|", 1)
                owned_by = parts[0]
                model_id_display = parts[1]
            elif "/" in model_id:
                parts = model_id.split("/", 1)
                owned_by = parts[0]
                model_id_display = model_id
            else:
                owned_by = "unknown"
                model_id_display = model_id

            models.append(Model(
                id=model_id_display,
                object="model",
                created=int(time.time()),
                owned_by=owned_by,
            ))

        return ModelList(object="list", data=models)

    def retrieve(self, model: str, **kwargs):
        """Retrieve a single model by ID."""
        from ..types import Model

        return Model(
            id=model,
            object="model",
            created=int(time.time()),
            owned_by=model.split("/")[0] if "/" in model else "unknown",
        )


class AsyncModels:
    """Async Models resource — await client.models.list(), await client.models.retrieve()"""

    def __init__(self, engine):
        self._engine = engine

    async def list(self, **kwargs):
        """List all available models asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._sync_list(**kwargs))

    def _sync_list(self, **kwargs):
        """Synchronous list implementation for executor."""
        from ..types import ModelList, Model

        try:
            from core.model_cache import shared_model_cache

            if not shared_model_cache.is_cache_valid():
                try:
                    self._engine._discover_and_cache_models_sync()
                except Exception as e:
                    logger.warning(f"Model discovery failed: {e}")

            if shared_model_cache.is_cache_valid():
                model_ids = shared_model_cache.get_models()
            else:
                model_ids = []
        except ImportError:
            model_ids = []

        models = []
        for model_id in model_ids:
            if "|" in model_id:
                parts = model_id.split("|", 1)
                owned_by = parts[0]
                model_id_display = parts[1]
            elif "/" in model_id:
                parts = model_id.split("/", 1)
                owned_by = parts[0]
                model_id_display = model_id
            else:
                owned_by = "unknown"
                model_id_display = model_id

            models.append(Model(
                id=model_id_display,
                object="model",
                created=int(time.time()),
                owned_by=owned_by,
            ))

        return ModelList(object="list", data=models)

    async def retrieve(self, model: str, **kwargs):
        """Retrieve a single model by ID asynchronously."""
        from ..types import Model

        return Model(
            id=model,
            object="model",
            created=int(time.time()),
            owned_by=model.split("/")[0] if "/" in model else "unknown",
        )
