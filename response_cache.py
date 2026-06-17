"""
Response caching module for AI Engine
Provides intelligent caching with semantic similarity
"""
import json
import hashlib
import time
import os
from typing import Dict, Any, Optional, List
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
        # Create a normalized representation
        normalized = {
            "messages": [{"role": m.get("role"), "content": m.get("content", "")} for m in messages],
            "model": model,
            "provider": provider
        }
        
        # Generate hash
        content = json.dumps(normalized, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, messages: List[Dict], model: str, provider: str = None) -> Optional[Dict]:
        """Get cached response if available"""
        cache_key = self._get_cache_key(messages, model, provider)
        
        with self._lock:
            # Check memory cache first
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                if time.time() < entry["expires_at"]:
                    self.stats["hits"] += 1
                    return entry["response"]
                else:
                    del self.memory_cache[cache_key]
            
            # Check disk cache
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, "r") as f:
                        entry = json.load(f)
                    if time.time() < entry["expires_at"]:
                        # Restore to memory cache
                        self.memory_cache[cache_key] = entry
                        self.stats["hits"] += 1
                        return entry["response"]
                    else:
                        cache_file.unlink()
                except (json.JSONDecodeError, KeyError):
                    cache_file.unlink()
            
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
            # Store in memory
            self.memory_cache[cache_key] = entry
            
            # Store on disk
            cache_file = self.cache_dir / f"{cache_key}.json"
            try:
                with open(cache_file, "w") as f:
                    json.dump(entry, f)
            except Exception as e:
                print(f"Warning: Failed to write cache to disk: {e}")
    
    def invalidate(self, messages: List[Dict], model: str, provider: str = None):
        """Invalidate a specific cache entry"""
        cache_key = self._get_cache_key(messages, model, provider)
        
        with self._lock:
            self.memory_cache.pop(cache_key, None)
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                cache_file.unlink()
    
    def clear(self):
        """Clear all cache"""
        with self._lock:
            self.memory_cache.clear()
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            self.stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def cleanup_expired(self):
        """Remove expired entries"""
        current_time = time.time()
        
        with self._lock:
            # Clean memory cache
            expired_keys = [
                key for key, entry in self.memory_cache.items()
                if current_time >= entry["expires_at"]
            ]
            for key in expired_keys:
                del self.memory_cache[key]
                self.stats["evictions"] += 1
            
            # Clean disk cache
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, "r") as f:
                        entry = json.load(f)
                    if current_time >= entry.get("expires_at", 0):
                        cache_file.unlink()
                        self.stats["evictions"] += 1
                except (json.JSONDecodeError, KeyError):
                    cache_file.unlink()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "evictions": self.stats["evictions"],
            "hit_rate": round(hit_rate, 4),
            "memory_entries": len(self.memory_cache),
            "disk_entries": len(list(self.cache_dir.glob("*.json")))
        }
    
    def find_similar(self, messages: List[Dict], threshold: float = 0.8) -> Optional[Dict]:
        """Find similar cached responses using simple string similarity"""
        # Simple implementation - could be enhanced with embeddings
        query_content = " ".join(m.get("content", "") for m in messages).lower()
        
        with self._lock:
            for entry in self.memory_cache.values():
                if time.time() >= entry["expires_at"]:
                    continue
                
                cached_messages = entry["response"].get("messages", [])
                cached_content = " ".join(m.get("content", "") for m in cached_messages).lower()
                
                # Simple similarity check
                if query_content and cached_content:
                    # Check if one contains the other or they share significant words
                    query_words = set(query_content.split())
                    cached_words = set(cached_content.split())
                    
                    if query_words and cached_words:
                        intersection = query_words & cached_words
                        union = query_words | cached_words
                        similarity = len(intersection) / len(union) if union else 0
                        
                        if similarity >= threshold:
                            return entry["response"]
        
        return None


# Global cache instance
response_cache = ResponseCache()
