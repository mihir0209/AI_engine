"""Tests for TUI model index search."""
from ai_engine.tui import ModelEntry, ModelIndex


def _index() -> ModelIndex:
    raw = [
        "github|azureml://registries/azureml-meta/models/Meta-Llama-3.1-405B-Instruct/versions/1",
        "groq|llama-3.3-70b-versatile",
        "openrouter|anthropic/claude-3.5-sonnet",
    ]
    return ModelIndex.build(raw)


def test_search_with_limit_none_and_query():
    index = _index()
    hits = index.search("llama", limit=None)
    assert hits
    assert all(isinstance(h, ModelEntry) for h in hits)


def test_search_empty_query_limit_none_returns_all():
    index = _index()
    assert len(index.search("", limit=None)) == 3
