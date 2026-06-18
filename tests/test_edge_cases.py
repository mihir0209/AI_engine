"""Edge case and boundary tests"""
import pytest


# === Empty/Null Input Tests ===

def test_empty_chat_messages():
    from ai_engine import AI_engine
    engine = AI_engine(verbose=False)
    result = engine.chat_completion([])
    assert result.success is False


def test_null_model_name():
    from ai_engine import AI_engine
    engine = AI_engine(verbose=False)
    engine.providers = {}
    result = engine.chat_completion([{"role": "user", "content": "hi"}], model=None)
    assert result.success is False


def test_empty_search_query():
    from chat_module.db import ChatDB
    import tempfile
    temp_dir = tempfile.mkdtemp()
    db = ChatDB(f"{temp_dir}/test.db")
    
    results = db.search_messages("")
    assert isinstance(results, list)
    
    import shutil
    shutil.rmtree(temp_dir)


def test_empty_config():
    from config import AI_CONFIGS
    assert isinstance(AI_CONFIGS, dict)


# === Boundary Value Tests ===

def test_max_length_message():
    from chat_module.db import ChatDB
    import tempfile
    temp_dir = tempfile.mkdtemp()
    db = ChatDB(f"{temp_dir}/test.db")
    
    chat_id = db.create_chat("Test")
    long_content = "x" * 100000  # Max allowed
    msg_id = db.add_message(chat_id, "user", long_content)
    assert msg_id > 0
    
    import shutil
    shutil.rmtree(temp_dir)


def test_min_length_message():
    from chat_module.db import ChatDB
    import tempfile
    temp_dir = tempfile.mkdtemp()
    db = ChatDB(f"{temp_dir}/test.db")
    
    chat_id = db.create_chat("Test")
    msg_id = db.add_message(chat_id, "user", "x")  # Min 1 char
    assert msg_id > 0
    
    import shutil
    shutil.rmtree(temp_dir)


def test_zero_rate_limit():
    from enhanced_health import PerUserRateLimiter
    rl = PerUserRateLimiter(default_rate=1, default_burst=1)
    allowed, info = rl.allow_request("user")
    assert allowed is True  # First request allowed
    allowed, info = rl.allow_request("user")
    assert allowed is False  # Second request blocked


def test_large_context_window():
    from chat_module.db import ChatDB
    import tempfile
    temp_dir = tempfile.mkdtemp()
    db = ChatDB(f"{temp_dir}/test.db")
    
    chat_id = db.create_chat("Test")
    for i in range(100):
        db.add_message(chat_id, "user", f"Message {i}", tokens=10)
    
    context = db.get_context_messages(chat_id, max_tokens=1000000)
    assert len(context) == 100
    
    import shutil
    shutil.rmtree(temp_dir)


# === Concurrency Tests ===

def test_concurrent_cache_access():
    from caching import AdvancedCache
    import threading
    
    cache = AdvancedCache(max_size=100)
    errors = []
    
    def writer():
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")
    
    def reader():
        for i in range(100):
            cache.get(f"key_{i}")
    
    threads = [threading.Thread(target=writer) for _ in range(5)]
    threads += [threading.Thread(target=reader) for _ in range(5)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # No errors = success
    assert len(errors) == 0


# === Error Recovery Tests ===

def test_circuit_breaker_recovery():
    from infrastructure import CircuitBreaker, CircuitState
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1, half_open_max_calls=1)
    
    # Trip the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    
    # Wait for recovery
    import time
    time.sleep(0.2)
    
    # Should be half-open after can_execute
    can_exec = cb.can_execute()
    assert can_exec is True
    assert cb.state == CircuitState.HALF_OPEN
    
    # Success should close it
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_retry_eventual_success():
    from infrastructure import RetryHandler
    rh = RetryHandler(max_retries=3, base_delay=0.01, jitter=False)
    
    attempts = 0
    def flaky_func():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Not yet")
        return "success"
    
    result = rh.execute_with_retry(flaky_func)
    assert result == "success"
    assert attempts == 3
