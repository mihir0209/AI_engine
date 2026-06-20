"""Tests for rate limit manager"""
import pytest
import time


def test_rate_limit_basic():
    from rate_limit_manager import RateLimitManager
    manager = RateLimitManager(default_limit=10)
    
    # Initially available
    assert manager.is_available("provider1") is True


def test_rate_limit_record():
    from rate_limit_manager import RateLimitManager
    manager = RateLimitManager(default_limit=10)
    
    for _ in range(5):
        manager.record_request("provider1")
    
    provider = manager.get_provider("provider1")
    assert provider.requests_made == 5


def test_rate_limit_mark_limited():
    from rate_limit_manager import RateLimitManager
    manager = RateLimitManager()
    
    manager.mark_rate_limited("provider1", retry_after=1)
    assert manager.is_available("provider1") is False


def test_rate_limit_recovery():
    from rate_limit_manager import RateLimitManager
    manager = RateLimitManager()
    
    manager.mark_rate_limited("provider1", retry_after=0.1)
    assert manager.is_available("provider1") is False
    
    time.sleep(0.2)
    assert manager.is_available("provider1") is True


def test_rate_limit_get_available():
    from rate_limit_manager import RateLimitManager
    manager = RateLimitManager()
    
    manager.mark_rate_limited("provider1", retry_after=60)
    
    available = manager.get_available_providers(["provider1", "provider2"])
    assert "provider1" not in available
    assert "provider2" in available


def test_rate_limit_stats():
    from rate_limit_manager import RateLimitManager
    manager = RateLimitManager()
    
    manager.record_request("provider1")
    manager.record_request("provider1")
    
    stats = manager.get_stats()
    assert "provider1" in stats
    assert stats["provider1"]["requests_made"] == 2


def test_rate_limit_reset():
    from rate_limit_manager import RateLimitManager
    manager = RateLimitManager()
    
    manager.mark_rate_limited("provider1", retry_after=60)
    manager.reset_provider("provider1")
    
    assert manager.is_available("provider1") is True


def test_rate_limit_window_reset():
    from rate_limit_manager import RateLimitManager
    manager = RateLimitManager()
    
    provider = manager.get_provider("provider1")
    provider.requests_made = 100
    provider.window_start = time.time() - 70  # Window expired
    
    provider.reset_window()
    assert provider.requests_made == 0
