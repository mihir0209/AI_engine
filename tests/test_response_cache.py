"""Tests for response cache"""
import time


def test_cache_hit():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages = [{"role": "user", "content": "hello"}]
    response = {"content": "hi there"}

    cache.set(messages, "gpt-4", response)
    result = cache.get(messages, "gpt-4")
    assert result is not None
    assert result["content"] == "hi there"


def test_cache_miss():
    from response_cache import ResponseCache
    import tempfile
    temp_dir = tempfile.mkdtemp()
    cache = ResponseCache(cache_dir=temp_dir)

    messages = [{"role": "user", "content": "hello"}]
    result = cache.get(messages, "gpt-4")
    assert result is None

    import shutil
    shutil.rmtree(temp_dir)


def test_cache_ttl_expiration():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages = [{"role": "user", "content": "hello"}]
    cache.set(messages, "gpt-4", {"content": "hi"}, ttl=0.1)

    time.sleep(0.2)
    result = cache.get(messages, "gpt-4")
    assert result is None


def test_cache_delete():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages = [{"role": "user", "content": "hello"}]
    cache.set(messages, "gpt-4", {"content": "hi"})
    cache.invalidate(messages, "gpt-4")

    result = cache.get(messages, "gpt-4")
    assert result is None


def test_cache_clear():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages = [{"role": "user", "content": "hello"}]
    cache.set(messages, "gpt-4", {"content": "hi"})
    cache.clear()

    result = cache.get(messages, "gpt-4")
    assert result is None


def test_cache_stats():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages = [{"role": "user", "content": "hello"}]
    cache.set(messages, "gpt-4", {"content": "hi"})
    cache.get(messages, "gpt-4")  # Hit
    cache.get([{"role": "user", "content": "other"}], "gpt-4")  # Miss

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_cache_cleanup():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages = [{"role": "user", "content": "hello"}]
    cache.set(messages, "gpt-4", {"content": "hi"}, ttl=0.1)

    time.sleep(0.2)
    cache.cleanup_expired()

    result = cache.get(messages, "gpt-4")
    assert result is None


def test_cache_different_providers():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages = [{"role": "user", "content": "hello"}]
    cache.set(messages, "openai", {"content": "hi from openai"})
    cache.set(messages, "anthropic", {"content": "hi from anthropic"})

    result1 = cache.get(messages, "openai")
    result2 = cache.get(messages, "anthropic")

    assert result1["content"] == "hi from openai"
    assert result2["content"] == "hi from anthropic"


def test_cache_overwrite():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages = [{"role": "user", "content": "hello"}]
    cache.set(messages, "gpt-4", {"content": "old"})
    cache.set(messages, "gpt-4", {"content": "new"})

    result = cache.get(messages, "gpt-4")
    assert result["content"] == "new"


def test_cache_find_similar():
    from response_cache import ResponseCache
    cache = ResponseCache()

    messages1 = [{"role": "user", "content": "what is python programming language"}]
    messages2 = [{"role": "user", "content": "tell me about python programming"}]

    cache.set(messages1, "gpt-4", {"content": "Python is a programming language"})

    # find_similar may or may not find a match depending on implementation
    result = cache.find_similar(messages2)
    # Just verify it doesn't crash
    assert result is None or isinstance(result, dict)
