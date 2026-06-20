"""
Latency tracker for AI providers
Tracks response times and adjusts provider priority
"""
import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime


@dataclass
class LatencyRecord:
    """Single latency measurement"""
    timestamp: float
    latency_ms: float
    success: bool
    model: str = ""


@dataclass
class ProviderLatency:
    """Latency stats for a provider"""
    provider: str
    total_requests: int = 0
    successful_requests: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    recent_latencies: List[float] = field(default_factory=list)
    
    # Model-specific latencies
    model_latencies: Dict[str, List[float]] = field(default_factory=dict)


class LatencyTracker:
    """Tracks latency per provider and adjusts priority"""
    
    def __init__(self, max_recent: int = 100, slow_threshold_ms: float = 5000):
        self.max_recent = max_recent
        self.slow_threshold_ms = slow_threshold_ms
        self.providers: Dict[str, ProviderLatency] = {}
        self._lock = threading.Lock()
    
    def record(self, provider: str, latency_ms: float, success: bool, model: str = ""):
        """Record a latency measurement"""
        with self._lock:
            if provider not in self.providers:
                self.providers[provider] = ProviderLatency(provider=provider)
            
            stats = self.providers[provider]
            stats.total_requests += 1
            stats.total_latency_ms += latency_ms
            stats.min_latency_ms = min(stats.min_latency_ms, latency_ms)
            stats.max_latency_ms = max(stats.max_latency_ms, latency_ms)
            
            if success:
                stats.successful_requests += 1
            
            # Keep recent latencies
            stats.recent_latencies.append(latency_ms)
            if len(stats.recent_latencies) > self.max_recent:
                stats.recent_latencies.pop(0)
            
            # Track per-model latency
            if model:
                if model not in stats.model_latencies:
                    stats.model_latencies[model] = []
                stats.model_latencies[model].append(latency_ms)
                if len(stats.model_latencies[model]) > self.max_recent:
                    stats.model_latencies[model].pop(0)
    
    def get_avg_latency(self, provider: str) -> float:
        """Get average latency for a provider"""
        with self._lock:
            if provider not in self.providers:
                return 0.0
            stats = self.providers[provider]
            if not stats.recent_latencies:
                return 0.0
            return sum(stats.recent_latencies) / len(stats.recent_latencies)
    
    def get_p95_latency(self, provider: str) -> float:
        """Get 95th percentile latency"""
        with self._lock:
            if provider not in self.providers:
                return 0.0
            stats = self.providers[provider]
            if not stats.recent_latencies:
                return 0.0
            sorted_lat = sorted(stats.recent_latencies)
            idx = int(len(sorted_lat) * 0.95)
            return sorted_lat[min(idx, len(sorted_lat) - 1)]
    
    def is_slow(self, provider: str) -> bool:
        """Check if provider is too slow"""
        avg = self.get_avg_latency(provider)
        return avg > self.slow_threshold_ms
    
    def get_priority_adjustment(self, provider: str) -> int:
        """Get priority adjustment based on latency (lower = better)"""
        avg = self.get_avg_latency(provider)
        if avg <= 0:
            return 0
        # Slower providers get higher priority number (lower priority)
        # 1-2 seconds: +0, 2-5 seconds: +2, 5+ seconds: +5
        if avg > 5000:
            return 5
        elif avg > 2000:
            return 2
        elif avg > 1000:
            return 1
        return 0
    
    def get_stats(self, provider: str = None) -> Dict:
        """Get latency statistics"""
        with self._lock:
            if provider:
                if provider not in self.providers:
                    return {}
                stats = self.providers[provider]
                
                # Calculate p95 locally to avoid deadlock
                p95 = 0.0
                if stats.recent_latencies:
                    sorted_lat = sorted(stats.recent_latencies)
                    idx = int(len(sorted_lat) * 0.95)
                    p95 = sorted_lat[min(idx, len(sorted_lat) - 1)]
                
                return {
                    "provider": provider,
                    "total_requests": stats.total_requests,
                    "avg_latency_ms": round(stats.total_latency_ms / max(1, stats.total_requests), 2),
                    "min_latency_ms": round(stats.min_latency_ms, 2) if stats.min_latency_ms != float('inf') else 0,
                    "max_latency_ms": round(stats.max_latency_ms, 2),
                    "p95_latency_ms": round(p95, 2),
                    "models": {m: len(lats) for m, lats in stats.model_latencies.items()}
                }
            else:
                result = {}
                for name, s in self.providers.items():
                    p95 = 0.0
                    if s.recent_latencies:
                        sorted_lat = sorted(s.recent_latencies)
                        idx = int(len(sorted_lat) * 0.95)
                        p95 = sorted_lat[min(idx, len(sorted_lat) - 1)]
                    
                    result[name] = {
                        "avg_latency_ms": round(s.total_latency_ms / max(1, s.total_requests), 2),
                        "p95_latency_ms": round(p95, 2),
                        "requests": s.total_requests
                    }
                return result


# Global instance
latency_tracker = LatencyTracker()
