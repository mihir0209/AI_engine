"""Battle-tested tests for request queue"""
import pytest
import time
import threading


@pytest.fixture
def queue():
    from request_queue import RequestQueue
    return RequestQueue(max_queue_size=10, max_wait_time=1)


# === Basic Queue Tests ===

def test_enqueue(queue):
    request_id = queue.enqueue("provider1", lambda: "result")
    assert request_id is not None
    assert queue.get_queue_size("provider1") == 1


def test_enqueue_multiple(queue):
    for i in range(5):
        queue.enqueue("provider1", lambda: f"result_{i}")
    assert queue.get_queue_size("provider1") == 5


def test_enqueue_different_providers(queue):
    queue.enqueue("provider1", lambda: "r1")
    queue.enqueue("provider2", lambda: "r2")
    assert queue.get_queue_size("provider1") == 1
    assert queue.get_queue_size("provider2") == 1
    assert queue.get_queue_size() == 2


# === Process Queue Tests ===

def test_process_queue(queue):
    queue.enqueue("provider1", lambda: "result")
    results = queue.process_queue("provider1")
    assert len(results) == 1
    assert results[0]["success"] is True
    assert results[0]["result"] == "result"


def test_process_queue_with_args(queue):
    def add(a, b):
        return a + b
    
    queue.enqueue("provider1", add, args=(2, 3))
    results = queue.process_queue("provider1")
    assert results[0]["result"] == 5


def test_process_queue_with_kwargs(queue):
    def greet(name, greeting="Hello"):
        return f"{greeting} {name}"
    
    queue.enqueue("provider1", greet, kwargs={"name": "World", "greeting": "Hi"})
    results = queue.process_queue("provider1")
    assert results[0]["result"] == "Hi World"


def test_process_queue_max_requests(queue):
    for i in range(5):
        queue.enqueue("provider1", lambda: f"result_{i}")
    
    results = queue.process_queue("provider1", max_requests=3)
    assert len(results) == 3
    assert queue.get_queue_size("provider1") == 2


def test_process_queue_error(queue):
    def failing():
        raise ValueError("Test error")
    
    queue.enqueue("provider1", failing)
    results = queue.process_queue("provider1")
    assert results[0]["success"] is False
    assert "Test error" in results[0]["error"]


def test_process_empty_queue(queue):
    results = queue.process_queue("nonexistent")
    assert results == []


# === Queue Size Tests ===

def test_get_queue_size(queue):
    queue.enqueue("p1", lambda: None)
    queue.enqueue("p1", lambda: None)
    queue.enqueue("p2", lambda: None)
    
    assert queue.get_queue_size("p1") == 2
    assert queue.get_queue_size("p2") == 1
    assert queue.get_queue_size() == 3


def test_max_queue_size(queue):
    for i in range(15):
        queue.enqueue("provider1", lambda: f"result_{i}")
    
    assert queue.get_queue_size("provider1") == 10  # Max queue size


# === Clear Queue Tests ===

def test_clear_queue_provider(queue):
    queue.enqueue("p1", lambda: None)
    queue.enqueue("p2", lambda: None)
    
    queue.clear_queue("p1")
    assert queue.get_queue_size("p1") == 0
    assert queue.get_queue_size("p2") == 1


def test_clear_all_queues(queue):
    queue.enqueue("p1", lambda: None)
    queue.enqueue("p2", lambda: None)
    
    queue.clear_queue()
    assert queue.get_queue_size() == 0


# === Expired Request Tests ===

def test_expired_request_skipped(queue):
    queue.enqueue("provider1", lambda: "result")
    
    # Manually expire the request
    queue.queues["provider1"][0].created_at = time.time() - 100
    
    results = queue.process_queue("provider1")
    assert len(results) == 0  # Expired request skipped


# === Stats Tests ===

def test_get_stats(queue):
    queue.enqueue("p1", lambda: None)
    queue.enqueue("p2", lambda: None)
    
    stats = queue.get_stats()
    assert stats["total_queued"] == 2
    assert "p1" in stats["by_provider"]
    assert "p2" in stats["by_provider"]


# === Thread Safety Tests ===

def test_concurrent_enqueue(queue):
    def enqueue_requests(provider):
        for i in range(20):
            queue.enqueue(provider, lambda: None)
    
    threads = [threading.Thread(target=enqueue_requests, args=(f"p{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3)
    
    # Each provider has max 10 items, so total should be 50 (5 providers * 10 max)
    assert queue.get_queue_size() == 50


def test_concurrent_process(queue):
    for i in range(10):
        queue.enqueue("provider1", lambda: None)
    
    def process():
        return queue.process_queue("provider1", max_requests=5)
    
    threads = [threading.Thread(target=process) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3)
    
    assert queue.get_queue_size() <= 10
