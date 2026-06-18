"""
Request/Response middleware for AI Engine
Provides logging, metrics, and request tracking
"""
import time
import uuid
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
import threading


@dataclass
class RequestMetrics:
    """Metrics for a single request"""
    request_id: str
    endpoint: str
    method: str
    start_time: float
    end_time: Optional[float] = None
    status_code: Optional[int] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    tokens_used: int = 0
    cost: float = 0.0
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "duration_ms": round(self.duration_ms, 2),
            "status_code": self.status_code,
            "provider": self.provider,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "cost": self.cost,
            "error": self.error,
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat()
        }


class MetricsCollector:
    """Collects and aggregates request metrics"""

    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.requests: List[RequestMetrics] = []
        self.counters: Dict[str, int] = {}
        self.timers: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def record_request(self, metrics: RequestMetrics):
        """Record a request's metrics"""
        with self._lock:
            self.requests.append(metrics)

            # Trim history
            if len(self.requests) > self.max_history:
                self.requests = self.requests[-self.max_history:]

            # Update counters
            endpoint = metrics.endpoint
            self.counters[f"{endpoint}_count"] = self.counters.get(f"{endpoint}_count", 0) + 1

            if metrics.status_code:
                status_key = f"{endpoint}_{metrics.status_code}"
                self.counters[status_key] = self.counters.get(status_key, 0) + 1

            # Update timers
            if endpoint not in self.timers:
                self.timers[endpoint] = []
            self.timers[endpoint].append(metrics.duration_ms)

            # Keep only recent timers
            if len(self.timers[endpoint]) > 1000:
                self.timers[endpoint] = self.timers[endpoint][-1000:]

    def get_endpoint_stats(self, endpoint: str) -> Dict:
        """Get statistics for an endpoint"""
        with self._lock:
            timers = self.timers.get(endpoint, [])
            count = self.counters.get(f"{endpoint}_count", 0)

            if not timers:
                return {"endpoint": endpoint, "count": count}

            sorted_timers = sorted(timers)
            return {
                "endpoint": endpoint,
                "count": count,
                "avg_ms": round(sum(timers) / len(timers), 2),
                "min_ms": round(min(timers), 2),
                "max_ms": round(max(timers), 2),
                "p50_ms": round(sorted_timers[len(sorted_timers) // 2], 2),
                "p95_ms": round(sorted_timers[int(len(sorted_timers) * 0.95)], 2)
            }

    def get_overall_stats(self) -> Dict:
        """Get overall statistics"""
        with self._lock:
            total_requests = len(self.requests)
            successful = sum(1 for r in self.requests if r.status_code and 200 <= r.status_code < 300)
            failed = sum(1 for r in self.requests if r.status_code and r.status_code >= 400)

            all_durations = [r.duration_ms for r in self.requests if r.duration_ms > 0]

            return {
                "total_requests": total_requests,
                "successful": successful,
                "failed": failed,
                "success_rate": round(successful / total_requests * 100, 2) if total_requests > 0 else 0,
                "avg_duration_ms": round(sum(all_durations) / len(all_durations), 2) if all_durations else 0,
                "endpoints": list(self.timers.keys())
            }

    def get_recent_requests(self, limit: int = 50) -> List[Dict]:
        """Get recent requests"""
        with self._lock:
            return [r.to_dict() for r in self.requests[-limit:]]


class RequestTracker:
    """Tracks request context through the request lifecycle"""

    _local = threading.local()

    @classmethod
    def start_request(cls, endpoint: str, method: str = "GET") -> RequestMetrics:
        """Start tracking a request"""
        metrics = RequestMetrics(
            request_id=str(uuid.uuid4()),
            endpoint=endpoint,
            method=method,
            start_time=time.time()
        )
        cls._local.current_request = metrics
        return metrics

    @classmethod
    def get_current(cls) -> Optional[RequestMetrics]:
        """Get current request metrics"""
        return getattr(cls._local, 'current_request', None)

    @classmethod
    def end_request(cls, status_code: int = 200, error: str = None):
        """End tracking a request"""
        metrics = cls.get_current()
        if metrics:
            metrics.end_time = time.time()
            metrics.status_code = status_code
            metrics.error = error

    @classmethod
    def set_provider(cls, provider: str, model: str = None):
        """Set provider info on current request"""
        metrics = cls.get_current()
        if metrics:
            metrics.provider = provider
            metrics.model = model

    @classmethod
    def set_tokens(cls, tokens: int, cost: float = 0.0):
        """Set token usage on current request"""
        metrics = cls.get_current()
        if metrics:
            metrics.tokens_used = tokens
            metrics.cost = cost


def tracked_request(endpoint: str):
    """Decorator to automatically track requests"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            metrics = RequestTracker.start_request(endpoint)
            try:
                result = func(*args, **kwargs)
                RequestTracker.end_request(status_code=200)
                return result
            except Exception as e:
                RequestTracker.end_request(status_code=500, error=str(e))
                raise
        return wrapper
    return decorator


# Global instances
metrics_collector = MetricsCollector()
