"""
Response caching module for AI Engine
Provides intelligent caching with semantic similarity
"""
import json
import hashlib
import time
from typing import Dict, Optional, List
from pathlib import Path
import threading


class ResponseCache:
    """Intelligent response cache with TTL and similarity matching"""

    def __init__(self, cache_dir: str = "cache", default_ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.default_ttl = default_ttl
        self.memory_cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _get_cache_key(self, messages: List[Dict], model: str, provider: str = None) -> str:
        """Generate cache key from request"""
        normalized = {
            "messages": [{"role": m.get("role"), "content": m.get("content", "")} for m in messages],
            "model": model,
            "provider": provider
        }
        content = json.dumps(normalized, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, messages: List[Dict], model: str, provider: str = None) -> Optional[Dict]:
        """Get cached response if available"""
        cache_key = self._get_cache_key(messages, model, provider)

        with self._lock:
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                if time.time() < entry["expires_at"]:
                    self.stats["hits"] += 1
                    return entry["response"]
                else:
                    del self.memory_cache[cache_key]

            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, "r") as f:
                        entry = json.load(f)
                    if time.time() < entry["expires_at"]:
                        self.memory_cache[cache_key] = entry
                        self.stats["hits"] += 1
                        return entry["response"]
                    else:
                        cache_file.unlink()
                except (json.JSONDecodeError, KeyError):
                    cache_file.unlink()

            try:
                from core.redis_cache import redis_cache
                remote = redis_cache.get(cache_key)
                if remote is not None:
                    self.memory_cache[cache_key] = {
                        "response": remote,
                        "expires_at": time.time() + self.default_ttl,
                    }
                    self.stats["hits"] += 1
                    return remote
            except Exception:
                pass

            self.stats["misses"] += 1
            return None

    def set(
        self,
        messages: List[Dict],
        model: str,
        response: Dict,
        provider: str = None,
        ttl: int = None
    ):
        """Cache a response"""
        cache_key = self._get_cache_key(messages, model, provider)
        ttl = ttl or self.default_ttl

        entry = {
            "response": response,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
            "model": model,
            "provider": provider
        }

        with self._lock:
            self.memory_cache[cache_key] = entry
            cache_file = self.cache_dir / f"{cache_key}.json"
            try:
                with open(cache_file, "w") as f:
                    json.dump(entry, f)
            except Exception as e:
                print(f"Warning: Failed to write cache to disk: {e}")

        try:
            from core.redis_cache import redis_cache
            redis_cache.set(cache_key, response, ttl=ttl)
        except Exception:
            pass

    def invalidate(self, messages: List[Dict], model: str, provider: str = None):
        """Invalidate a specific cache entry"""
        cache_key = self._get_cache_key(messages, model, provider)

        with self._lock:
            self.memory_cache.pop(cache_key, None)
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                cache_file.unlink()
        try:
            from core.redis_cache import redis_cache
            redis_cache.delete(cache_key)
        except Exception:
            pass

    def clear(self):
        """Clear all cache"""
        with self._lock:
            self.memory_cache.clear()
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0
        return {
            **self.stats,
            "hit_rate": hit_rate,
            "size": len(self.memory_cache),
            "disk_entries": len(list(self.cache_dir.glob("*.json")))
        }

    def cleanup_expired(self):
        """Remove expired entries"""
        now = time.time()
        with self._lock:
            expired_keys = [
                k for k, v in self.memory_cache.items()
                if now >= v["expires_at"]
            ]
            for key in expired_keys:
                del self.memory_cache[key]
                self.stats["evictions"] += 1

            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, "r") as f:
                        entry = json.load(f)
                    if now >= entry["expires_at"]:
                        cache_file.unlink()
                        self.stats["evictions"] += 1
                except (json.JSONDecodeError, KeyError):
                    cache_file.unlink()

    def find_similar(self, messages: List[Dict], model: str = None, threshold: float = 0.9) -> Optional[Dict]:
        """Find similar cached responses (simple text matching)"""
        if not messages:
            return None

        query = " ".join(str(m.get("content", "")) for m in messages).lower()
        query_words = set(query.split())

        best_match = None
        best_score = 0

        with self._lock:
            for entry in self.memory_cache.values():
                if time.time() >= entry["expires_at"]:
                    continue
                if model is not None and entry.get("model") != model:
                    continue

                cached_msgs = entry.get("response", {})
                # Compare against stored messages in key space is hard; use response content
                content = str(cached_msgs)
                words = set(content.lower().split())
                if not words or not query_words:
                    continue
                score = len(query_words & words) / len(query_words | words)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = entry["response"]

        return best_match


# Global instance
response_cache = ResponseCache()
