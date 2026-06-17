"""Tests for advanced caching and deduplication"""
import pytest
import time
import threading


# === Advanced Cache Tests ===

def test_lru_cache_basic():
    from caching import AdvancedCache, EvictionPolicy
    cache = AdvancedCache(max_size=3, eviction_policy=EvictionPolicy.LRU)
    
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    
    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_lru_cache_eviction():
    from caching import AdvancedCache, EvictionPolicy
    cache = AdvancedCache(max_size=3, eviction_policy=EvictionPolicy.LRU)
    
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.get("a")  # Access "a" to make it recent
    cache.set("d", 4)  # Should evict "b" (least recently used)
    
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3
    assert cache.get("d") == 4


def test_ttl_cache_expiration():
    from caching import AdvancedCache, EvictionPolicy
    cache = AdvancedCache(max_size=10, eviction_policy=EvictionPolicy.TTL)
    
    cache.set("a", 1, ttl=0.1)
    assert cache.get("a") == 1
    
    time.sleep(0.2)
    assert cache.get("a") is None


def test_cache_delete():
    from caching import AdvancedCache
    cache = AdvancedCache(max_size=10)
    
    cache.set("a", 1)
    assert cache.delete("a") is True
    assert cache.get("a") is None
    assert cache.delete("a") is False


def test_cache_clear():
    from caching import AdvancedCache
    cache = AdvancedCache(max_size=10)
    
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_cache_stats():
    from caching import AdvancedCache
    cache = AdvancedCache(max_size=10)
    
    cache.set("a", 1)
    cache.get("a")  # Hit
    cache.get("b")  # Miss
    
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 50.0


def test_cache_get_keys():
    from caching import AdvancedCache
    cache = AdvancedCache(max_size=10)
    
    cache.set("a", 1)
    cache.set("b", 2)
    
    keys = cache.get_keys()
    assert "a" in keys
    assert "b" in keys


def test_lfu_eviction():
    from caching import AdvancedCache, EvictionPolicy
    cache = AdvancedCache(max_size=3, eviction_policy=EvictionPolicy.LFU)
    
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    
    # Access "a" multiple times
    cache.get("a")
    cache.get("a")
    cache.get("a")
    
    # Access "b" once
    cache.get("b")
    
    # Add new item - should evict "c" (least frequently used)
    cache.set("d", 4)
    
    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") is None


# === Request Deduplicator Tests ===

def test_deduplicator_register():
    from caching import RequestDeduplicator
    dedup = RequestDeduplicator()
    
    assert dedup.register_request("req_1") is True
    assert dedup.register_request("req_1") is False  # Duplicate


def test_deduplicator_complete():
    from caching import RequestDeduplicator
    dedup = RequestDeduplicator(timeout=1)
    
    def wait_for_result():
        return dedup.wait_for_result("req_1")
    
    # Start waiter in thread
    t = threading.Thread(target=wait_for_result)
    t.start()
    
    time.sleep(0.1)
    dedup.complete_request("req_1", "result")
    t.join(timeout=2)


def test_deduplicator_stats():
    from caching import RequestDeduplicator
    dedup = RequestDeduplicator()
    
    dedup.register_request("req_1")
    dedup.register_request("req_2")
    
    stats = dedup.get_stats()
    assert stats["pending_requests"] == 2


def test_deduplicator_is_duplicate():
    from caching import RequestDeduplicator
    dedup = RequestDeduplicator()
    
    assert dedup.is_duplicate("req_1") is False
    dedup.register_request("req_1")
    assert dedup.is_duplicate("req_1") is True
