"""
Provider health monitoring for AI Engine
Tracks uptime, response times, and auto-disables failing providers
"""
import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque


@dataclass
class HealthRecord:
    """Single health check record"""
    timestamp: float
    success: bool
    response_time: float = 0.0
    error: Optional[str] = None
    status_code: Optional[int] = None


@dataclass
class ProviderHealth:
    """Health status for a provider"""
    provider: str
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    consecutive_failures: int = 0
    last_check: Optional[float] = None
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    avg_response_time: float = 0.0
    uptime_percent: float = 100.0
    status: str = "unknown"  # healthy, degraded, unhealthy, unknown
    
    # Recent history (last 100 checks)
    recent_checks: List[HealthRecord] = field(default_factory=list)


class HealthMonitor:
    """Monitors provider health and auto-manages provider status"""
    
    def __init__(self, failure_threshold: int = 5, recovery_time: int = 300):
        """
        Args:
            failure_threshold: Consecutive failures before marking unhealthy
            recovery_time: Seconds to wait before retrying unhealthy providers
        """
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.providers: Dict[str, ProviderHealth] = {}
        self._lock = threading.Lock()
    
    def register_provider(self, provider_name: str):
        """Register a provider for health monitoring"""
        with self._lock:
            if provider_name not in self.providers:
                self.providers[provider_name] = ProviderHealth(provider=provider_name)
    
    def record_check(self, provider_name: str, success: bool, response_time: float = 0.0,
                     error: str = None, status_code: int = None):
        """Record a health check result"""
        with self._lock:
            if provider_name not in self.providers:
                self.providers[provider_name] = ProviderHealth(provider=provider_name)
            
            health = self.providers[provider_name]
            
            # Record the check
            record = HealthRecord(
                timestamp=time.time(),
                success=success,
                response_time=response_time,
                error=error,
                status_code=status_code
            )
            
            health.recent_checks.append(record)
            if len(health.recent_checks) > 100:
                health.recent_checks.pop(0)
            
            # Update counters
            health.total_checks += 1
            health.last_check = time.time()
            
            if success:
                health.successful_checks += 1
                health.consecutive_failures = 0
                health.last_success = time.time()
                health.status = "healthy"
            else:
                health.failed_checks += 1
                health.consecutive_failures += 1
                health.last_failure = time.time()
                
                # Update status based on consecutive failures
                if health.consecutive_failures >= self.failure_threshold:
                    health.status = "unhealthy"
                else:
                    health.status = "degraded"
            
            # Calculate uptime percentage
            if health.total_checks > 0:
                health.uptime_percent = (health.successful_checks / health.total_checks) * 100
            
            # Calculate average response time from recent checks
            recent_times = [c.response_time for c in health.recent_checks if c.success and c.response_time > 0]
            if recent_times:
                health.avg_response_time = sum(recent_times) / len(recent_times)
    
    def is_provider_healthy(self, provider_name: str) -> bool:
        """Check if a provider is healthy enough to use"""
        with self._lock:
            if provider_name not in self.providers:
                return True  # Unknown providers are assumed healthy
            
            health = self.providers[provider_name]
            
            # If unhealthy, check if recovery time has passed
            if health.status == "unhealthy":
                if health.last_failure:
                    time_since_failure = time.time() - health.last_failure
                    if time_since_failure >= self.recovery_time:
                        # Allow retry after recovery time
                        health.status = "degraded"
                        return True
                return False
            
            return True
    
    def _provider_health_dict(self, health: ProviderHealth) -> Dict:
        """Build provider health response (caller must hold _lock)."""
        return {
            "provider": health.provider,
            "status": health.status,
            "uptime_percent": round(health.uptime_percent, 2),
            "total_checks": health.total_checks,
            "successful": health.successful_checks,
            "failed": health.failed_checks,
            "consecutive_failures": health.consecutive_failures,
            "avg_response_time": round(health.avg_response_time, 3),
            "last_check": datetime.fromtimestamp(health.last_check).isoformat() if health.last_check else None,
            "last_success": datetime.fromtimestamp(health.last_success).isoformat() if health.last_success else None,
            "last_failure": datetime.fromtimestamp(health.last_failure).isoformat() if health.last_failure else None,
        }

    def get_provider_health(self, provider_name: str) -> Dict:
        """Get health status for a provider"""
        with self._lock:
            if provider_name not in self.providers:
                return {"status": "unknown", "uptime_percent": 0}

            return self._provider_health_dict(self.providers[provider_name])

    def get_all_health(self) -> Dict[str, Dict]:
        """Get health status for all providers"""
        with self._lock:
            return {
                name: self._provider_health_dict(health)
                for name, health in self.providers.items()
            }
    
    def get_healthy_providers(self) -> List[str]:
        """Get list of healthy provider names"""
        with self._lock:
            return [name for name, health in self.providers.items() if health.status == "healthy"]
    
    def get_unhealthy_providers(self) -> List[str]:
        """Get list of unhealthy provider names"""
        with self._lock:
            return [name for name, health in self.providers.items() if health.status == "unhealthy"]
    
    def get_summary(self) -> Dict:
        """Get overall health summary"""
        with self._lock:
            total = len(self.providers)
            healthy = sum(1 for h in self.providers.values() if h.status == "healthy")
            degraded = sum(1 for h in self.providers.values() if h.status == "degraded")
            unhealthy = sum(1 for h in self.providers.values() if h.status == "unhealthy")
            
            # Get lists without calling other locked methods
            healthiest = [name for name, h in self.providers.items() if h.status == "healthy"][:5]
            unhealthy_list = [name for name, h in self.providers.items() if h.status == "unhealthy"]
            
            return {
                "total": total,
                "healthy": healthy,
                "degraded": degraded,
                "unhealthy": unhealthy,
                "healthiest": healthiest,
                "unhealthy_list": unhealthy_list
            }
    
    def reset_provider(self, provider_name: str):
        """Reset health status for a provider"""
        with self._lock:
            if provider_name in self.providers:
                self.providers[provider_name] = ProviderHealth(provider=provider_name)


# Global instance
health_monitor = HealthMonitor()
