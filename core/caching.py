"""
Advanced caching strategies for AI Engine
LRU, TTL, and size-based eviction policies
"""
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import OrderedDict
from enum import Enum


class EvictionPolicy(Enum):
    """Cache eviction policies"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In First Out


@dataclass
class CacheEntry:
    """Single cache entry"""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: Optional[float] = None  # TTL in seconds

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class AdvancedCache:
    """Cache with multiple eviction policies"""

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[float] = None,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.eviction_policy = eviction_policy
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self.cache:
                self.stats["misses"] += 1
                return None

            entry = self.cache[key]

            # Check TTL expiration
            if entry.is_expired():
                del self.cache[key]
                self.stats["misses"] += 1
                return None

            # Update access metadata
            entry.last_accessed = time.time()
            entry.access_count += 1

            # Move to end for LRU
            if self.eviction_policy == EvictionPolicy.LRU:
                self.cache.move_to_end(key)

            self.stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float = None):
        """Set value in cache"""
        with self._lock:
            # Remove if exists (to update position)
            if key in self.cache:
                del self.cache[key]

            # Evict if at capacity
            while len(self.cache) >= self.max_size:
                self._evict()

            # Add new entry
            self.cache[key] = CacheEntry(
                key=key,
                value=value,
                ttl=ttl or self.default_ttl
            )

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self):
        """Clear entire cache"""
        with self._lock:
            self.cache.clear()
            self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _evict(self):
        """Evict entry based on policy"""
        if not self.cache:
            return

        if self.eviction_policy == EvictionPolicy.LRU:
            # Remove first (oldest accessed)
            self.cache.popitem(last=False)
        elif self.eviction_policy == EvictionPolicy.LFU:
            # Remove least frequently used
            min_key = min(self.cache.keys(), key=lambda k: self.cache[k].access_count)
            del self.cache[min_key]
        elif self.eviction_policy == EvictionPolicy.FIFO:
            # Remove first inserted
            self.cache.popitem(last=False)
        elif self.eviction_policy == EvictionPolicy.TTL:
            # Remove expired entries first
            for key in list(self.cache.keys()):
                if self.cache[key].is_expired():
                    del self.cache[key]
                    return
            # If no expired, fall back to LRU
            self.cache.popitem(last=False)

        self.stats["evictions"] += 1

    def cleanup_expired(self):
        """Remove all expired entries"""
        with self._lock:
            expired_keys = [k for k, v in self.cache.items() if v.is_expired()]
            for key in expired_keys:
                del self.cache[key]

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self._lock:
            total_requests = self.stats["hits"] + self.stats["misses"]
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "evictions": self.stats["evictions"],
                "hit_rate": round(self.stats["hits"] / total_requests * 100, 2) if total_requests > 0 else 0,
                "eviction_policy": self.eviction_policy.value
            }

    def get_keys(self) -> List[str]:
        """Get all cache keys"""
        with self._lock:
            return list(self.cache.keys())


class RequestDeduplicator:
    """Deduplicates identical concurrent requests"""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.pending: Dict[str, threading.Event] = {}
        self.results: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def is_duplicate(self, request_key: str) -> bool:
        """Check if this is a duplicate request"""
        with self._lock:
            return request_key in self.pending

    def wait_for_result(self, request_key: str) -> Any:
        """Wait for result from duplicate request"""
        event = self.pending.get(request_key)
        if event:
            event.wait(timeout=self.timeout)
            return self.results.get(request_key)
        return None

    def register_request(self, request_key: str) -> bool:
        """Register a request, returns True if first request"""
        with self._lock:
            if request_key in self.pending:
                return False

            self.pending[request_key] = threading.Event()
            return True

    def complete_request(self, request_key: str, result: Any):
        """Complete a request and notify waiters"""
        with self._lock:
            self.results[request_key] = result
            event = self.pending.pop(request_key, None)
            if event:
                event.set()

    def get_stats(self) -> Dict:
        """Get deduplication statistics"""
        with self._lock:
            return {
                "pending_requests": len(self.pending),
                "cached_results": len(self.results)
            }


# Global instances
lru_cache = AdvancedCache(max_size=1000, eviction_policy=EvictionPolicy.LRU)
ttl_cache = AdvancedCache(max_size=500, default_ttl=300, eviction_policy=EvictionPolicy.TTL)
request_deduplicator = RequestDeduplicator()
