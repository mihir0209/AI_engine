"""Shared provider failure policy with exponential backoff and configurable fallback chains."""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_RETRYABLE_ERRORS = frozenset(
    {
        "rate_limit",
        "auth_error",
        "quota_exceeded",
        "service_unavailable",
        "server_error",
        "network_error",
        "unknown",
    }
)


@dataclass
class ProviderRetryPolicy:
    """Retry configuration for a single provider."""
    retries: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    backoff_multiplier: float = 2.0

    def compute_delay(self, attempt: int) -> float:
        delay = self.backoff_base * (self.backoff_multiplier ** attempt)
        return min(delay, self.backoff_max)


@dataclass
class FallbackChain:
    """Ordered list of provider names to try after a primary provider fails."""
    providers: List[str] = field(default_factory=list)

    def next(self, current: str, available: set[str]) -> Optional[str]:
        idx = self.providers.index(current) if current in self.providers else -1
        for candidate in self.providers[idx + 1:]:
            if candidate in available:
                return candidate
        return None


FALLBACK_CHAINS: Dict[str, FallbackChain] = {
    "groq": FallbackChain(["groq", "openrouter", "cerebras", "nvidia", "together"]),
    "gemini": FallbackChain(["gemini", "openrouter", "cerebras", "nvidia", "together"]),
    "openrouter": FallbackChain(["openrouter", "groq", "cerebras", "nvidia", "together"]),
    "cerebras": FallbackChain(["cerebras", "groq", "openrouter", "nvidia", "together"]),
    "nvidia": FallbackChain(["nvidia", "groq", "openrouter", "cerebras", "together"]),
    "together": FallbackChain(["together", "openrouter", "groq", "cerebras", "nvidia"]),
    "cohere": FallbackChain(["cohere", "groq", "openrouter"]),
    "mistral": FallbackChain(["mistral", "groq", "openrouter", "cerebras"]),
    "deepseek": FallbackChain(["deepseek", "openrouter", "groq"]),
    "fireworks": FallbackChain(["fireworks", "groq", "openrouter"]),
    "cloudflare": FallbackChain(["cloudflare", "groq", "openrouter"]),
    "default": FallbackChain(),
}

DEFAULT_RETRY_POLICY = ProviderRetryPolicy()

_PROVIDER_RETRY_POLICIES: Dict[str, ProviderRetryPolicy] = {
    "groq": ProviderRetryPolicy(retries=4, backoff_base=1.0),
    "gemini": ProviderRetryPolicy(retries=4, backoff_base=2.0),
    "openrouter": ProviderRetryPolicy(retries=3, backoff_base=1.5),
    "cerebras": ProviderRetryPolicy(retries=4, backoff_base=1.0),
    "nvidia": ProviderRetryPolicy(retries=3, backoff_base=1.5),
}


class BackoffTracker:
    """Thread-safe exponential backoff state per provider."""
    def __init__(self):
        self._attempts: Dict[str, int] = {}
        self._last_attempt: Dict[str, float] = {}
        self._lock = threading.Lock()

    def record_attempt(self, provider: str) -> float:
        """Record a failure attempt, return the backoff delay to wait."""
        policy = _PROVIDER_RETRY_POLICIES.get(provider, DEFAULT_RETRY_POLICY)
        with self._lock:
            attempt = self._attempts.get(provider, 0)
            delay = policy.compute_delay(attempt)
            self._attempts[provider] = attempt + 1
            self._last_attempt[provider] = time.time()
            return delay

    def reset(self, provider: str):
        """Reset backoff state after a successful request."""
        with self._lock:
            self._attempts.pop(provider, None)
            self._last_attempt.pop(provider, None)

    def get_attempt_count(self, provider: str) -> int:
        with self._lock:
            return self._attempts.get(provider, 0)


backoff_tracker = BackoffTracker()


def should_retry_provider(error_type: str) -> bool:
    """Return whether routing should continue with another provider."""
    return error_type in _RETRYABLE_ERRORS


def get_fallback_chain(provider_name: str) -> FallbackChain:
    return FALLBACK_CHAINS.get(provider_name, FALLBACK_CHAINS["default"])


def get_retry_policy(provider_name: str) -> ProviderRetryPolicy:
    return _PROVIDER_RETRY_POLICIES.get(provider_name, DEFAULT_RETRY_POLICY)
