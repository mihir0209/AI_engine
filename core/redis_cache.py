"""Optional Redis-backed response cache.

Enabled when REDIS_URL is set. Falls back gracefully if redis is missing.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

_client = None
_init_attempted = False


def get_redis_client():
    global _client, _init_attempted
    if _init_attempted:
        return _client
    _init_attempted = True
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis  # type: ignore
        _client = redis.Redis.from_url(url, decode_responses=True)
        _client.ping()
        return _client
    except Exception:
        _client = None
        return None


class RedisResponseCache:
    """Simple string JSON cache with TTL."""

    def __init__(self, prefix: str = "ai_engine:cache:", default_ttl: int = 3600):
        self.prefix = prefix
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        client = get_redis_client()
        if not client:
            return None
        try:
            raw = client.get(self.prefix + key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        client = get_redis_client()
        if not client:
            return False
        try:
            client.setex(self.prefix + key, ttl or self.default_ttl, json.dumps(value))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        client = get_redis_client()
        if not client:
            return False
        try:
            client.delete(self.prefix + key)
            return True
        except Exception:
            return False


redis_cache = RedisResponseCache()
