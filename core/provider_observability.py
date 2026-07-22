"""Read-only provider reliability snapshots for operator-facing views."""

import time
from collections.abc import Iterable
from typing import Any

from core.health_monitor import health_monitor
from core.infrastructure import circuit_breakers
from core.latency_tracker import latency_tracker
from core.rate_limit_manager import rate_limit_manager
from core.usage_tracker import usage_tracker


def _health_snapshot(provider_name: str) -> dict[str, Any]:
    health = health_monitor.get_provider_health(provider_name)
    return {
        "status": health.get("status", "unknown"),
        "uptime_percent": health.get("uptime_percent", 0.0),
        "total_checks": health.get("total_checks", 0),
        "successful": health.get("successful", 0),
        "failed": health.get("failed", 0),
        "consecutive_failures": health.get("consecutive_failures", 0),
        "last_check": health.get("last_check"),
    }


def _latency_snapshot(provider_name: str) -> dict[str, Any]:
    latency = latency_tracker.get_stats(provider_name)
    return {
        "avg_latency_ms": latency.get("avg_latency_ms", 0.0),
        "p95_latency_ms": latency.get("p95_latency_ms", 0.0),
        "total_requests": latency.get("total_requests", 0),
    }


def _rate_limit_snapshot(provider_name: str) -> dict[str, Any]:
    provider = rate_limit_manager.providers.get(provider_name)
    if provider is None:
        return {
            "is_limited": False,
            "available": True,
            "requests_made": 0,
            "requests_limit": rate_limit_manager.default_limit,
            "retry_after": 0,
        }

    is_limited = provider.is_rate_limited and time.time() <= provider.rate_limit_until
    return {
        "is_limited": is_limited,
        "available": not is_limited,
        "requests_made": provider.requests_made,
        "requests_limit": provider.requests_limit,
        "retry_after": provider.retry_after if provider.is_rate_limited else 0,
    }


def _usage_snapshot(provider_name: str) -> dict[str, Any]:
    usage = usage_tracker.get_provider_stats(provider_name, hours=24)
    return {
        "requests": usage.get("requests", 0),
        "successful": usage.get("successful", 0),
        "failed": usage.get("failed", 0),
        "success_rate": usage.get("success_rate", 0),
        "avg_response_time": usage.get("avg_response_time", 0),
    }


def _circuit_snapshot(provider_name: str) -> dict[str, Any]:
    breaker = circuit_breakers.get(f"provider:{provider_name}")
    if breaker is None:
        return {
            "state": "unknown",
            "failure_count": 0,
            "success_count": 0,
            "last_failure_time": None,
            "last_state_change": None,
        }

    state = breaker.get_state()
    return {
        "state": state["state"],
        "failure_count": state["failure_count"],
        "success_count": state["success_count"],
        "last_failure_time": state["last_failure_time"],
        "last_state_change": state["last_state_change"],
    }


def get_provider_snapshot(provider_name: str) -> dict[str, Any]:
    """Return a stable, side-effect-free reliability snapshot."""
    return {
        "provider": provider_name,
        "health": _health_snapshot(provider_name),
        "latency": _latency_snapshot(provider_name),
        "rate_limit": _rate_limit_snapshot(provider_name),
        "usage": _usage_snapshot(provider_name),
        "circuit": _circuit_snapshot(provider_name),
    }


def get_all_provider_snapshots(provider_names: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Return snapshots keyed by provider name."""
    return {name: get_provider_snapshot(name) for name in provider_names}
