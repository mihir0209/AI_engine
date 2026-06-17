"""Tests for model_cache.py module"""
import os
import json
import time
import pytest

from model_cache import ModelCache, shared_model_cache


@pytest.fixture
def model_cache(tmp_path):
    cache = ModelCache()
    cache.cache_file = str(tmp_path / "test_cache.json")
    return cache


def test_model_cache_init(model_cache):
    assert model_cache.cache_data["cached_at"] is None
    assert model_cache.cache_data["models"] == []
    assert model_cache.cache_data["providers"] == {}


def test_model_cache_is_cache_valid_empty(model_cache):
    assert model_cache.is_cache_valid() is False


def test_model_cache_save_and_load(model_cache):
    models = ["provider1/gpt-4", "provider2/claude-3"]
    model_cache.save_cache(models)
    assert model_cache.is_cache_valid() is True

    loaded_models = model_cache.get_models()
    assert len(loaded_models) == 2
    assert "provider1/gpt-4" in loaded_models


def test_model_cache_save_dict_format(model_cache):
    models = [{"id": "gpt-4", "object": "model"}, {"id": "claude-3", "object": "model"}]
    model_cache.save_cache(models)
    loaded = model_cache.get_models()
    assert "gpt-4" in loaded
    assert "claude-3" in loaded


def test_model_cache_expiration(model_cache):
    model_cache.save_cache(["model1"])
    # Manually set cache time to past
    model_cache.cache_data["cached_at"] = time.time() - (model_cache.cache_duration + 1)
    assert model_cache.is_cache_valid() is False


def test_model_cache_get_cache_age(model_cache):
    assert model_cache.get_cache_age() == float('inf')

    model_cache.save_cache(["model1"])
    age = model_cache.get_cache_age()
    assert age >= 0
    assert age < 1


def test_model_cache_get_providers_data(model_cache):
    providers = {"p1": {"models": ["m1"]}}
    model_cache.save_cache(["m1"], providers_data=providers)
    assert model_cache.get_providers_data() == providers


def test_model_cache_find_providers_pipe_format(model_cache):
    models = ["openai|gpt-4", "anthropic|claude-3", "openai|gpt-3.5"]
    model_cache.save_cache(models)

    results = model_cache.find_providers_for_model("gpt-4")
    assert len(results) == 1
    assert results[0][0] == "openai"


def test_model_cache_find_providers_slash_format(model_cache):
    models = ["openai/gpt-4", "anthropic/claude-3"]
    model_cache.save_cache(models)

    results = model_cache.find_providers_for_model("gpt-4")
    assert len(results) == 1
    assert results[0][0] == "openai"


def test_model_cache_find_providers_no_match(model_cache):
    models = ["openai|gpt-4", "anthropic|claude-3"]
    model_cache.save_cache(models)

    results = model_cache.find_providers_for_model("llama-3")
    assert len(results) == 0


def test_model_cache_find_providers_strict_match(model_cache):
    models = ["openai|gpt-4", "openai|gpt-4-turbo"]
    model_cache.save_cache(models)

    # Should only match exact "gpt-4", not "gpt-4-turbo"
    results = model_cache.find_providers_for_model("gpt-4")
    assert len(results) == 1
    assert results[0][1] == "gpt-4"


def test_model_cache_normalize_model_name(model_cache):
    assert model_cache._normalize_model_name("GPT-4") == "gpt4"
    assert model_cache._normalize_model_name("claude_3") == "claude3"
    assert model_cache._normalize_model_name("model.name") == "modelname"
    assert model_cache._normalize_model_name("") == ""
    assert model_cache._normalize_model_name(None) == ""


def test_model_cache_find_providers_deduplication(model_cache):
    models = ["openai|gpt-4", "openai|gpt-4"]
    model_cache.save_cache(models)
    results = model_cache.find_providers_for_model("gpt-4")
    assert len(results) == 1


def test_model_cache_thread_safety(model_cache):
    import threading
    model_cache.save_cache(["model1"])

    def read_cache():
        for _ in range(100):
            model_cache.get_models()
            model_cache.is_cache_valid()

    threads = [threading.Thread(target=read_cache) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_model_cache_load_from_file(model_cache):
    cache_data = {
        "cached_at": time.time(),
        "models": ["p1|m1", "p2|m2"],
        "providers": {}
    }
    with open(model_cache.cache_file, "w") as f:
        json.dump(cache_data, f)

    loaded = model_cache.load_cache()
    assert loaded is True
    assert len(model_cache.get_models()) == 2


def test_model_cache_load_expired_file(model_cache):
    cache_data = {
        "cached_at": time.time() - 99999,
        "models": ["p1|m1"],
        "providers": {}
    }
    with open(model_cache.cache_file, "w") as f:
        json.dump(cache_data, f)

    loaded = model_cache.load_cache()
    assert loaded is False


def test_model_cache_load_nonexistent(model_cache):
    model_cache.cache_file = "/nonexistent/path/cache.json"
    loaded = model_cache.load_cache()
    assert loaded is False


def test_shared_model_cache_exists():
    assert shared_model_cache is not None
    assert isinstance(shared_model_cache, ModelCache)
