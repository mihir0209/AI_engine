"""Shared AI Engine singleton — initialized once, used by all SDK classes."""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("ai_engine")

_global_config: Dict[str, Any] = {}
_engine_instance = None


def _load_config_json(config_path: str = None) -> Dict[str, Any]:
    """Load config from JSON file."""
    if config_path:
        path = Path(config_path)
    else:
        # Default: config.json next to this package
        path = Path(__file__).parent / "config.json"

    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _resolve_config(config=None, cdn_config=None, **kwargs) -> Dict[str, Any]:
    """Merge config from: JSON file → constructor args → env vars → defaults."""
    # 1. Load from config.json
    if isinstance(config, str):
        base = _load_config_json(config)
    elif isinstance(config, dict):
        base = config.copy()
    else:
        base = _load_config_json()

    # 2. Merge global config
    base.update(_global_config)

    # 3. Merge constructor kwargs
    if "api_keys" in kwargs:
        base.setdefault("api_keys", {}).update(kwargs["api_keys"])
    for key in ("timeout", "max_retries", "default_provider"):
        if key in kwargs:
            base[key] = kwargs[key]
    if cdn_config is not None:
        base["cdn_config_url"] = cdn_config

    # 4. Environment variable overrides
    env_prefix = "AI_ENGINE_"
    env_map = {
        "AI_ENGINE_CDN_CONFIG": "cdn_config_url",
        "AI_ENGINE_TIMEOUT": "timeout",
        "AI_ENGINE_DEFAULT_PROVIDER": "default_provider",
    }
    for env_var, config_key in env_map.items():
        val = os.environ.get(env_var)
        if val is not None:
            base[config_key] = int(val) if config_key == "timeout" else val

    # 5. API key env vars: AI_ENGINE_API_KEY_{PROVIDER}
    for env_key, env_val in os.environ.items():
        if env_key.startswith("AI_ENGINE_API_KEY_"):
            provider = env_key[len("AI_ENGINE_API_KEY_"):].lower()
            base.setdefault("api_keys", {})[provider] = env_val

    return base


def _init_engine(config: Dict[str, Any]):
    """Initialize AI_engine from merged config."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.ai_engine import AI_engine

    # Apply provider overrides
    engine = AI_engine(verbose=False)

    # Set API keys from config
    api_keys = config.get("api_keys", {})
    for provider_name, key in api_keys.items():
        if provider_name in engine.providers:
            engine.providers[provider_name]["api_keys"] = [key]
            engine.providers[provider_name]["enabled"] = True

    # Apply provider priority/enable overrides
    provider_overrides = config.get("providers", {})
    for provider_name, overrides in provider_overrides.items():
        if provider_name in engine.providers:
            for k, v in overrides.items():
                engine.providers[provider_name][k] = v

    return engine


def get_engine(config=None, **kwargs):
    """Get or create the shared engine singleton."""
    global _engine_instance
    if _engine_instance is None:
        resolved = _resolve_config(config, **kwargs)
        _engine_instance = _init_engine(resolved)
    return _engine_instance


def set_engine(engine):
    """Manually set the engine singleton."""
    global _engine_instance
    _engine_instance = engine


def reset_engine():
    """Reset the engine (for testing)."""
    global _engine_instance
    _engine_instance = None


# Re-export for convenience
class AIEngine:
    """Advanced AI Engine client with provider-specific features."""
    pass
