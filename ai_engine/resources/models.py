"""Models resource — wraps AI_engine model discovery."""
import time
from typing import Optional


class Models:
    """Models resource — client.models.list(), client.models.retrieve()"""

    def __init__(self, engine):
        self._engine = engine

    def list(self, **kwargs):
        """List all available models."""
        from ..types import ModelList, Model

        # Use shared model cache for fast listing
        try:
            from core.model_cache import shared_model_cache
            if shared_model_cache.is_cache_valid():
                model_ids = shared_model_cache.get_models()
            else:
                model_ids = []
        except ImportError:
            model_ids = []

        models = []
        for model_id in model_ids:
            parts = model_id.split("/", 1)
            owned_by = parts[0] if len(parts) > 1 else "unknown"
            models.append(Model(
                id=model_id,
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
