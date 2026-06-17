"""Tests for intelligent router and response cache"""
import pytest
import time
import tempfile
import shutil


# === Intelligent Router Tests ===

def test_detect_task_type_coding():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    messages = [{"role": "user", "content": "Write a Python function to sort a list"}]
    assert router.detect_task_type(messages) == "coding"


def test_detect_task_type_writing():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    messages = [{"role": "user", "content": "Write an essay about climate change"}]
    assert router.detect_task_type(messages) == "writing"


def test_detect_task_type_math():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    messages = [{"role": "user", "content": "Calculate the integral of x^2"}]
    assert router.detect_task_type(messages) == "math"


def test_detect_task_type_translation():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    messages = [{"role": "user", "content": "Translate this to French"}]
    assert router.detect_task_type(messages) == "translation"


def test_detect_task_type_summary():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    messages = [{"role": "user", "content": "Please summarize this document for me"}]
    assert router.detect_task_type(messages) == "summarization"


def test_detect_task_type_quick():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    messages = [{"role": "user", "content": "Hi"}]
    assert router.detect_task_type(messages) == "quick"


def test_get_task_profile():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    profile = router.get_task_profile("coding")
    assert profile.task_type == "coding"
    assert "gpt-4" in profile.recommended_models


def test_calculate_model_score():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    profile = router.get_task_profile("coding")
    score = router.calculate_model_score("gpt-4", "openai", profile)
    assert 0 <= score <= 1


def test_estimate_cost():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    cost = router.estimate_cost("openai", "gpt-4", 1000, 500)
    assert cost > 0


def test_get_cost_comparison():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    
    comparisons = router.get_cost_comparison("coding")
    assert len(comparisons) > 0
    assert all("estimated_cost" in c for c in comparisons)


# === Response Cache Tests ===

@pytest.fixture
def cache():
    from response_cache import ResponseCache
    temp_dir = tempfile.mkdtemp()
    cache = ResponseCache(cache_dir=temp_dir)
    yield cache
    shutil.rmtree(temp_dir)


def test_cache_set_and_get(cache):
    messages = [{"role": "user", "content": "Hello"}]
    response = {"content": "Hi there!"}
    
    cache.set(messages, "gpt-4", response)
    result = cache.get(messages, "gpt-4")
    
    assert result is not None
    assert result["content"] == "Hi there!"


def test_cache_miss(cache):
    messages = [{"role": "user", "content": "Hello"}]
    result = cache.get(messages, "gpt-4")
    assert result is None


def test_cache_expiry(cache):
    messages = [{"role": "user", "content": "Hello"}]
    response = {"content": "Hi there!"}
    
    cache.set(messages, "gpt-4", response, ttl=1)  # 1 second TTL
    time.sleep(1.5)
    
    result = cache.get(messages, "gpt-4")
    assert result is None


def test_cache_invalidate(cache):
    messages = [{"role": "user", "content": "Hello"}]
    response = {"content": "Hi there!"}
    
    cache.set(messages, "gpt-4", response)
    cache.invalidate(messages, "gpt-4")
    result = cache.get(messages, "gpt-4")
    assert result is None


def test_cache_clear(cache):
    messages = [{"role": "user", "content": "Hello"}]
    response = {"content": "Hi there!"}
    
    cache.set(messages, "gpt-4", response)
    cache.clear()
    result = cache.get(messages, "gpt-4")
    assert result is None


def test_cache_stats(cache):
    messages = [{"role": "user", "content": "Hello"}]
    response = {"content": "Hi there!"}
    
    # Miss
    cache.get(messages, "gpt-4")
    
    # Set and hit
    cache.set(messages, "gpt-4", response)
    cache.get(messages, "gpt-4")
    
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_cache_cleanup_expired(cache):
    messages1 = [{"role": "user", "content": "Hello"}]
    messages2 = [{"role": "user", "content": "World"}]
    
    cache.set(messages1, "gpt-4", {"content": "Hi"}, ttl=1)
    cache.set(messages2, "gpt-4", {"content": "Hey"}, ttl=3600)
    
    time.sleep(1.5)
    cache.cleanup_expired()
    
    assert cache.get(messages1, "gpt-4") is None
    assert cache.get(messages2, "gpt-4") is not None
