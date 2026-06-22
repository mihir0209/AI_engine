"""
Usage tracking for AI Engine
Tracks requests, tokens, and costs per provider
"""
import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class UsageRecord:
    """Single usage record"""
    timestamp: float
    provider: str
    model: str
    success: bool
    response_time: float
    tokens_used: int = 0
    cost: float = 0.0


class UsageTracker:
    """Tracks API usage for billing and analytics"""
    
    def __init__(self, max_records: int = 10000):
        self.max_records = max_records
        self.records: List[UsageRecord] = []
        self._lock = threading.Lock()
    
    def record(self, provider: str, model: str, success: bool, 
               response_time: float, tokens: int = 0, cost: float = 0.0):
        """Record a usage event"""
        with self._lock:
            record = UsageRecord(
                timestamp=time.time(),
                provider=provider,
                model=model,
                success=success,
                response_time=response_time,
                tokens_used=tokens,
                cost=cost
            )
            self.records.append(record)
            
            # Trim old records
            if len(self.records) > self.max_records:
                self.records = self.records[-self.max_records:]
    
    def get_stats(self, hours: int = 24) -> Dict:
        """Get usage statistics for the last N hours"""
        cutoff = time.time() - (hours * 3600)
        
        with self._lock:
            recent = [r for r in self.records if r.timestamp > cutoff]
            
            if not recent:
                return {"total_requests": 0, "by_provider": {}, "by_model": {}}
            
            # By provider
            by_provider = defaultdict(lambda: {"requests": 0, "success": 0, "failed": 0, "tokens": 0, "cost": 0.0, "avg_time": 0.0})
            for r in recent:
                by_provider[r.provider]["requests"] += 1
                if r.success:
                    by_provider[r.provider]["success"] += 1
                else:
                    by_provider[r.provider]["failed"] += 1
                by_provider[r.provider]["tokens"] += r.tokens_used
                by_provider[r.provider]["cost"] += r.cost
                by_provider[r.provider]["avg_time"] += r.response_time
            
            # Calculate averages
            for provider in by_provider:
                if by_provider[provider]["requests"] > 0:
                    by_provider[provider]["avg_time"] = round(
                        by_provider[provider]["avg_time"] / by_provider[provider]["requests"] * 1000, 2
                    )
            
            # By model
            by_model = defaultdict(lambda: {"requests": 0, "success": 0, "tokens": 0, "cost": 0.0})
            for r in recent:
                by_model[r.model]["requests"] += 1
                if r.success:
                    by_model[r.model]["success"] += 1
                by_model[r.model]["tokens"] += r.tokens_used
                by_model[r.model]["cost"] += r.cost
            
            return {
                "total_requests": len(recent),
                "successful": sum(1 for r in recent if r.success),
                "failed": sum(1 for r in recent if not r.success),
                "total_tokens": sum(r.tokens_used for r in recent),
                "total_cost": round(sum(r.cost for r in recent), 6),
                "avg_response_time": round(sum(r.response_time for r in recent) / len(recent) * 1000, 2),
                "by_provider": dict(by_provider),
                "by_model": dict(by_model)
            }
    
    def get_provider_stats(self, provider: str, hours: int = 24) -> Dict:
        """Get usage stats for a specific provider"""
        cutoff = time.time() - (hours * 3600)
        
        with self._lock:
            records = [r for r in self.records if r.provider == provider and r.timestamp > cutoff]
            
            if not records:
                return {"requests": 0, "success_rate": 0}
            
            successful = sum(1 for r in records if r.success)
            
            return {
                "requests": len(records),
                "successful": successful,
                "failed": len(records) - successful,
                "success_rate": round(successful / len(records) * 100, 2),
                "total_tokens": sum(r.tokens_used for r in records),
                "total_cost": round(sum(r.cost for r in records), 6),
                "avg_response_time": round(sum(r.response_time for r in records) / len(records) * 1000, 2)
            }


# Global instance
usage_tracker = UsageTracker()
