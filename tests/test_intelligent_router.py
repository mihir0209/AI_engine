"""Tests for intelligent router"""
import pytest


# === Task Detection Tests ===

def test_detect_task_coding():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    messages = [{"role": "user", "content": "Write a Python function to sort a list"}]
    assert router.detect_task_type(messages) == "coding"


def test_detect_task_writing():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    messages = [{"role": "user", "content": "Write an essay about climate change"}]
    assert router.detect_task_type(messages) == "writing"


def test_detect_task_math():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    messages = [{"role": "user", "content": "Calculate the integral of x^2"}]
    assert router.detect_task_type(messages) == "math"


def test_detect_task_translation():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    messages = [{"role": "user", "content": "Translate this to French"}]
    assert router.detect_task_type(messages) == "translation"


def test_detect_task_summarization():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    messages = [{"role": "user", "content": "Please summarize this document"}]
    assert router.detect_task_type(messages) == "summarization"


def test_detect_task_quick():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    messages = [{"role": "user", "content": "Hi"}]
    assert router.detect_task_type(messages) == "quick"


def test_detect_task_empty():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    assert router.detect_task_type([]) == "quick"


# === Task Profile Tests ===

def test_get_task_profile():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    profile = router.get_task_profile("coding")
    assert profile.task_type == "coding"
    assert "gpt-4" in profile.recommended_models


def test_get_task_profile_unknown():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    profile = router.get_task_profile("unknown")
    assert profile.task_type == "quick"  # Default


# === Cost Estimation Tests ===

def test_estimate_cost():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    cost = router.estimate_cost("openai", "gpt-4", 1000, 500)
    assert cost > 0


def test_estimate_cost_unknown_provider():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    cost = router.estimate_cost("unknown", "model", 1000, 500)
    assert cost == 0.0


def test_get_cost_comparison():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    comparison = router.get_cost_comparison("coding")
    assert len(comparison) > 0
    assert all("estimated_cost" in c for c in comparison)


# === A/B Testing Tests ===

def test_create_ab_test():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    router.create_ab_test("test1", ["openai", "anthropic"], [0.5, 0.5])
    assert "test1" in router.ab_tests


def test_select_ab_test_provider():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    router.create_ab_test("test1", ["openai", "anthropic"], [0.7, 0.3])
    
    results = set()
    for _ in range(100):
        provider = router.select_ab_test_provider("test1")
        results.add(provider)
    
    assert len(results) == 2  # Both should be selected at some point


def test_record_ab_test_result():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    router.create_ab_test("test1", ["openai"], [1.0])
    router.record_ab_test_result("test1", "openai", True, 0.5)
    
    results = router.get_ab_test_results("test1")
    assert results["total_requests"] == 1


def test_get_ab_test_results():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    results = router.get_ab_test_results("nonexistent")
    assert results == {}


# === Latency Tracking Tests ===

def test_record_latency():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    router.record_latency("openai", "gpt-4", 0.5, True)
    
    stats = router.get_latency_stats()
    assert "openai/gpt-4" in stats


def test_get_latency_stats():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    router.record_latency("openai", "gpt-4", 0.5, True)
    router.record_latency("openai", "gpt-4", 0.8, True)
    
    stats = router.get_latency_stats("openai")
    assert len(stats) == 1


# === Provider Scoring Tests ===

def test_calculate_model_score():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    profile = router.get_task_profile("coding")
    score = router.calculate_model_score("gpt-4", "openai", profile)
    assert 0 <= score <= 1


def test_select_optimal_provider():
    from intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    messages = [{"role": "user", "content": "Write code"}]
    providers = [("openai", {"model": "gpt-4"}), ("anthropic", {"model": "claude-3"})]
    
    provider, model, profile = router.select_optimal_provider(messages, providers)
    assert provider in ["openai", "anthropic"]
