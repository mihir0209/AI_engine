"""Tests for batch processing, model search, and model cache"""
import pytest


# === Model Cache Tests ===

def test_model_cache_init():
    from core.model_cache import ModelCache
    cache = ModelCache()
    assert cache.is_cache_valid() is False
    assert len(cache.get_models()) == 0


def test_model_cache_save_and_load(tmp_path):
    from core.model_cache import ModelCache
    cache_file = str(tmp_path / "test_cache.json")
    cache = ModelCache()
    cache.cache_file = cache_file
    
    models = ["groq/llama-3.3-70b", "openai/gpt-4", "gemini/gemini-2.5-flash"]
    cache.save_cache(models)
    
    assert cache.is_cache_valid() is True
    assert len(cache.get_models()) == 3


def test_model_cache_find_providers():
    from core.model_cache import ModelCache
    cache = ModelCache()
    cache.save_cache(["groq/llama-3.3-70b", "openai/gpt-4", "groq/mistral"])
    
    results = cache.find_providers_for_model("llama-3.3-70b")
    assert len(results) == 1
    assert results[0][0] == "groq"


def test_model_cache_expiration(tmp_path):
    from core.model_cache import ModelCache
    import time
    cache_file = str(tmp_path / "test_cache.json")
    cache = ModelCache()
    cache.cache_file = cache_file
    
    cache.save_cache(["test/model"])
    assert cache.is_cache_valid() is True
    
    # Manually expire
    cache.cache_data["cached_at"] = time.time() - (cache.cache_duration + 1)
    assert cache.is_cache_valid() is False


# === Batch Processor Tests ===

def test_batch_processor_init():
    from core.batch import BatchProcessor
    from unittest.mock import MagicMock
    
    engine = MagicMock()
    processor = BatchProcessor(engine, max_concurrent=5)
    assert processor.max_concurrent == 5


def test_batch_processor_empty():
    import asyncio
    from core.batch import BatchProcessor
    from unittest.mock import MagicMock
    
    engine = MagicMock()
    processor = BatchProcessor(engine)
    
    result = asyncio.run(processor.process_batch([]))
    assert result == []


def test_batch_processor_single():
    import asyncio
    from core.batch import BatchProcessor
    from unittest.mock import MagicMock
    
    engine = MagicMock()
    engine.chat_completion.return_value = MagicMock(
        success=True, content="Hello", provider_used="test", model_used="test", response_time=0.1
    )
    
    processor = BatchProcessor(engine)
    result = asyncio.run(processor.process_batch([
        {"messages": [{"role": "user", "content": "Hi"}]}
    ]))
    
    assert len(result) == 1
    assert result[0]["success"] is True
    assert result[0]["content"] == "Hello"


def test_batch_processor_multiple():
    import asyncio
    from core.batch import BatchProcessor
    from unittest.mock import MagicMock
    
    engine = MagicMock()
    engine.chat_completion.return_value = MagicMock(
        success=True, content="Response", provider_used="test", model_used="test", response_time=0.1
    )
    
    processor = BatchProcessor(engine)
    requests_list = [
        {"messages": [{"role": "user", "content": f"Message {i}"}]}
        for i in range(5)
    ]
    
    result = asyncio.run(processor.process_batch(requests_list))
    assert len(result) == 5
    assert all(r["success"] for r in result)


def test_batch_processor_with_model():
    import asyncio
    from core.batch import BatchProcessor
    from unittest.mock import MagicMock
    
    engine = MagicMock()
    engine.chat_completion.return_value = MagicMock(
        success=True, content="Response", provider_used="test", model_used="gpt-4", response_time=0.1
    )
    
    processor = BatchProcessor(engine)
    result = asyncio.run(processor.process_batch(
        [{"messages": [{"role": "user", "content": "Hi"}]}],
        model="gpt-4"
    ))
    
    assert result[0]["model"] == "gpt-4"


def test_batch_processor_error_handling():
    import asyncio
    from core.batch import BatchProcessor
    from unittest.mock import MagicMock
    
    engine = MagicMock()
    engine.chat_completion.side_effect = Exception("Test error")
    
    processor = BatchProcessor(engine)
    result = asyncio.run(processor.process_batch([
        {"messages": [{"role": "user", "content": "Hi"}]}
    ]))
    
    assert result[0]["success"] is False
    assert "Test error" in result[0]["error"]


def test_batch_processor_max_requests():
    import asyncio
    from core.batch import BatchProcessor
    from unittest.mock import MagicMock
    
    engine = MagicMock()
    engine.chat_completion.return_value = MagicMock(
        success=True, content="Response", provider_used="test", model_used="test", response_time=0.1
    )
    
    processor = BatchProcessor(engine)
    requests_list = [
        {"messages": [{"role": "user", "content": f"Message {i}"}]}
        for i in range(150)  # More than max 100
    ]
    
    result = asyncio.run(processor.process_batch(requests_list))
    assert len(result) == 100  # Should be capped at 100


# === Model Search Tests ===

def test_model_search_filter_provider():
    from core.model_cache import ModelCache
    cache = ModelCache()
    cache.save_cache([
        "groq/llama-3.3-70b",
        "openai/gpt-4",
        "groq/mistral",
        "gemini/gemini-2.5-flash"
    ])
    
    # Filter by provider
    groq_models = [m for m in cache.get_models() if m.startswith("groq/")]
    assert len(groq_models) == 2


def test_model_search_filter_name():
    from core.model_cache import ModelCache
    cache = ModelCache()
    cache.save_cache([
        "groq/llama-3.3-70b",
        "openai/gpt-4",
        "groq/mistral",
        "gemini/gemini-2.5-flash"
    ])
    
    # Search by name
    llama_models = [m for m in cache.get_models() if "llama" in m.lower()]
    assert len(llama_models) == 1


def test_model_search_combined():
    from core.model_cache import ModelCache
    cache = ModelCache()
    cache.save_cache([
        "groq/llama-3.3-70b",
        "openai/gpt-4",
        "groq/mistral",
        "gemini/gemini-2.5-flash"
    ])
    
    # Combined filter
    results = [m for m in cache.get_models() 
               if m.startswith("groq/") and "llama" in m.lower()]
    assert len(results) == 1
    assert results[0] == "groq/llama-3.3-70b"


def test_model_search_no_match():
    from core.model_cache import ModelCache
    cache = ModelCache()
    cache.save_cache(["groq/llama-3.3-70b", "openai/gpt-4"])
    
    results = [m for m in cache.get_models() if "nonexistent" in m.lower()]
    assert len(results) == 0
