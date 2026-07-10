"""
Rate limit manager for AI Engine
Tracks rate limits and automatically recovers when limits reset
"""
import time
import threading
from typing import Dict, List
from dataclasses import dataclass, field


@dataclass
class RateLimitInfo:
    """Rate limit information for a provider"""
    provider: str
    is_rate_limited: bool = False
    rate_limit_until: float = 0.0
    requests_made: int = 0
    requests_limit: int = 60  # Default 60 RPM
    window_start: float = field(default_factory=time.time)
    retry_after: int = 0

    def reset_window(self):
        """Reset the rate limit window"""
        self.window_start = time.time()
        self.requests_made = 0

    def record_request(self):
        """Record a request"""
        self.requests_made += 1

    def is_available(self) -> bool:
        """Check if provider is available (not rate limited)"""
        if not self.is_rate_limited:
            return True

        # Check if rate limit has expired
        if time.time() > self.rate_limit_until:
            self.is_rate_limited = False
            self.reset_window()
            return True

        return False

    def mark_rate_limited(self, retry_after: int = 60):
        """Mark provider as rate limited"""
        self.is_rate_limited = True
        self.rate_limit_until = time.time() + retry_after
        self.retry_after = retry_after


class RateLimitManager:
    """Manages rate limits for all providers"""

    def __init__(self, default_limit: int = 60):
        self.default_limit = default_limit
        self.providers: Dict[str, RateLimitInfo] = {}
        self._lock = threading.Lock()

    def get_provider(self, provider_name: str) -> RateLimitInfo:
        """Get or create rate limit info for a provider"""
        with self._lock:
            if provider_name not in self.providers:
                self.providers[provider_name] = RateLimitInfo(
                    provider=provider_name,
                    requests_limit=self.default_limit
                )
            return self.providers[provider_name]

    def is_available(self, provider_name: str) -> bool:
        """Check if a provider is available (atomic check+reset)"""
        with self._lock:
            if provider_name not in self.providers:
                self.providers[provider_name] = RateLimitInfo(
                    provider=provider_name,
                    requests_limit=self.default_limit
                )
            provider = self.providers[provider_name]
            if not provider.is_rate_limited:
                return True
            if time.time() > provider.rate_limit_until:
                provider.is_rate_limited = False
                provider.reset_window()
                return True
            return False

    def record_request(self, provider_name: str):
        """Record a request to a provider"""
        provider = self.get_provider(provider_name)
        provider.record_request()

    def mark_rate_limited(self, provider_name: str, retry_after: int = 60):
        """Mark a provider as rate limited"""
        provider = self.get_provider(provider_name)
        provider.mark_rate_limited(retry_after)

    def get_available_providers(self, provider_names: List[str]) -> List[str]:
        """Get list of available (not rate limited) providers"""
        available = []
        for name in provider_names:
            if self.is_available(name):
                available.append(name)
        return available

    def get_stats(self) -> Dict:
        """Get rate limit statistics"""
        with self._lock:
            return {
                name: {
                    "is_rate_limited": p.is_rate_limited,
                    "requests_made": p.requests_made,
                    "requests_limit": p.requests_limit,
                    "retry_after": p.retry_after if p.is_rate_limited else 0,
                    "available": p.is_available()
                }
                for name, p in self.providers.items()
            }

    def reset_provider(self, provider_name: str):
        """Reset rate limit for a provider"""
        with self._lock:
            if provider_name in self.providers:
                self.providers[provider_name].reset_window()
                self.providers[provider_name].is_rate_limited = False


# Global instance
rate_limit_manager = RateLimitManager()
