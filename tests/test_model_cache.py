"""Tests for shared model cache sanitization."""
from core.model_cache import (
    format_cache_entry,
    normalize_discovered_model_id,
    sanitize_model_cache_entry,
    sanitize_model_list,
)


def test_normalize_discovered_model_id_from_dict():
    assert normalize_discovered_model_id({"id": "gpt-4o"}) == "gpt-4o"
    assert normalize_discovered_model_id({"name": "models/gemini-2.5-flash"}) == "gemini-2.5-flash"


def test_normalize_rejects_stringified_metadata():
    blob = "{'id': 'command-a', 'summary': 'Long description...'}"
    assert normalize_discovered_model_id(blob) is None


def test_sanitize_model_cache_entry_pipe_format():
    assert sanitize_model_cache_entry("groq|llama-3.3-70b-versatile") == (
        "groq|llama-3.3-70b-versatile"
    )


def test_sanitize_model_list_drops_invalid_rows():
    raw = [
        "groq|llama-3.3-70b-versatile",
        "cohere|{'id': 'bad', 'summary': 'oops'}",
        "groq|llama-3.3-70b-versatile",
    ]
    assert sanitize_model_list(raw) == ["groq|llama-3.3-70b-versatile"]


def test_format_cache_entry():
    assert format_cache_entry("openrouter", "google/gemini-2.5-flash") == (
        "openrouter|google/gemini-2.5-flash"
    )