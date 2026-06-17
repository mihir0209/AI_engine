"""
Enhanced health checks and per-user rate limiting
"""
import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict


class HealthCheckRegistry:
    """Registry for health checks"""
    
    def __init__(self):
        self.checks: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def register(self, name: str, check_func, timeout: int = 5):
        """Register a health check"""
        with self._lock:
            self.checks[name] = {
                "func": check_func,
                "timeout": timeout,
                "last_result": None,
                "last_run": None
            }
    
    def run_check(self, name: str) -> Dict:
        """Run a specific health check"""
        check = self.checks.get(name)
        if not check:
            return {"status": "unknown", "error": f"Check '{name}' not found"}
        
        try:
            result = check["func"]()
            status = "healthy" if result else "unhealthy"
            check["last_result"] = status
            check["last_run"] = datetime.now().isoformat()
            return {"status": status, "timestamp": check["last_run"]}
        except Exception as e:
            check["last_result"] = "error"
            check["last_run"] = datetime.now().isoformat()
            return {"status": "error", "error": str(e), "timestamp": check["last_run"]}
    
    def run_all(self) -> Dict:
        """Run all health checks"""
        results = {}
        overall_healthy = True
        
        for name in self.checks:
            result = self.run_check(name)
            results[name] = result
            if result["status"] != "healthy":
                overall_healthy = False
        
        return {
            "status": "healthy" if overall_healthy else "degraded",
            "checks": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_last_results(self) -> Dict:
        """Get last results without running checks"""
        return {
            name: {
                "status": check["last_result"],
                "last_run": check["last_run"]
            }
            for name, check in self.checks.items()
        }


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting"""
    tokens: float
    last_refill: float
    capacity: int
    refill_rate: float  # tokens per second


class PerUserRateLimiter:
    """Rate limiter per user/API key"""
    
    def __init__(
        self,
        default_rate: int = 60,
        default_burst: int = 10,
        window_seconds: int = 60
    ):
        self.default_rate = default_rate
        self.default_burst = default_burst
        self.window_seconds = window_seconds
        self.buckets: Dict[str, RateLimitBucket] = {}
        self.user_configs: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def configure_user(self, user_id: str, rate: int = None, burst: int = None):
        """Configure rate limits for a specific user"""
        with self._lock:
            self.user_configs[user_id] = {
                "rate": rate or self.default_rate,
                "burst": burst or self.default_burst
            }
    
    def _get_bucket(self, user_id: str) -> RateLimitBucket:
        """Get or create rate limit bucket for user"""
        with self._lock:
            if user_id not in self.buckets:
                config = self.user_configs.get(user_id, {})
                rate = config.get("rate", self.default_rate)
                burst = config.get("burst", self.default_burst)
                
                self.buckets[user_id] = RateLimitBucket(
                    tokens=float(burst),
                    last_refill=time.time(),
                    capacity=burst,
                    refill_rate=rate / self.window_seconds
                )
            
            return self.buckets[user_id]
    
    def _refill_tokens(self, bucket: RateLimitBucket):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - bucket.last_refill
        new_tokens = elapsed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + new_tokens)
        bucket.last_refill = now
    
    def allow_request(self, user_id: str, tokens: int = 1) -> Tuple[bool, Dict]:
        """Check if request is allowed"""
        bucket = self._get_bucket(user_id)
        
        with self._lock:
            self._refill_tokens(bucket)
            
            if bucket.tokens >= tokens:
                bucket.tokens -= tokens
                return True, {
                    "remaining": int(bucket.tokens),
                    "limit": bucket.capacity,
                    "reset_in": self.window_seconds
                }
            else:
                return False, {
                    "remaining": 0,
                    "limit": bucket.capacity,
                    "retry_after": int((tokens - bucket.tokens) / bucket.refill_rate) + 1
                }
    
    def get_usage(self, user_id: str) -> Dict:
        """Get current usage for a user"""
        bucket = self._get_bucket(user_id)
        
        with self._lock:
            self._refill_tokens(bucket)
            return {
                "remaining": int(bucket.tokens),
                "limit": bucket.capacity,
                "used": bucket.capacity - int(bucket.tokens)
            }
    
    def reset(self, user_id: str):
        """Reset rate limit for a user"""
        with self._lock:
            if user_id in self.buckets:
                del self.buckets[user_id]


# Global instances
health_registry = HealthCheckRegistry()
rate_limiter = PerUserRateLimiter()
