#!/usr/bin/env python3
"""Battle test: AI Synapse SDK end-to-end.

Run full live suite:  python tests/test_sdk_battle.py
Pytest (live only):   AI_ENGINE_MODE=all pytest tests/test_sdk_battle.py -m live -v
"""
import sys
import os
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0
errors = []

def _run_battle(name, func):
    global passed, failed
    try:
        func()
        passed += 1
        print(f"  PASS  {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  FAIL  {name}: {e}")


# === 1. Import Tests ===

def _battle_import_openai():
    from ai_engine import OpenAI
    assert OpenAI is not None

def _battle_import_async():
    from ai_engine import AsyncOpenAI
    assert AsyncOpenAI is not None

def _battle_import_anthropic():
    from ai_engine import Anthropic
    assert Anthropic is not None

def _battle_import_exceptions():
    from ai_engine._exceptions import OpenAIError, BadRequestError, AuthenticationError, RateLimitError, InternalServerError
    assert issubclass(BadRequestError, OpenAIError)
    assert issubclass(AuthenticationError, OpenAIError)
    assert issubclass(RateLimitError, OpenAIError)
    assert issubclass(InternalServerError, OpenAIError)

def _battle_import_engine():
    from ai_engine import AIEngine
    assert AIEngine is not None

def _battle_import_version():
    import ai_engine
    assert hasattr(ai_engine, "__version__")
    from ai_engine._version import get_version
    assert ai_engine.__version__ == get_version()


# === 2. Client Initialization Tests ===

def _battle_default_init():
    from ai_engine import OpenAI
    client = OpenAI()
    assert client._engine is not None
    assert len(client._engine.providers) > 0

def _battle_init_with_api_keys():
    from ai_engine import OpenAI
    client = OpenAI(api_keys={"groq": "test-key"})
    assert client._engine.providers["groq"]["api_keys"] == ["test-key"]

def _battle_init_with_config_dict():
    from ai_engine import OpenAI
    client = OpenAI(config={"timeout": 60, "default_provider": "groq"})
    assert client._engine is not None

def _battle_init_with_config_file():
    from ai_engine import OpenAI
    client = OpenAI(config="ai_engine/config.json")
    assert len(client._engine.providers) > 0

def _battle_use_method():
    import ai_engine
    ai_engine.use(api_keys={"test": "value"})
    assert ai_engine._global_config.get("api_keys", {}).get("test") == "value"


# === 3. Chat Completion Tests ===

def _battle_chat_non_streaming():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say exactly: battle test passed"}],
        max_tokens=10,
    )
    assert r.id.startswith("chatcmpl-")
    assert r.object == "chat.completion"
    assert isinstance(r.created, int)
    assert r.choices[0].message.role == "assistant"
    assert r.choices[0].message.content is not None
    assert r.choices[0].finish_reason == "stop"
    assert r.usage.total_tokens > 0
    assert r.usage.prompt_tokens + r.usage.completion_tokens == r.usage.total_tokens

def _battle_chat_streaming():
    from ai_engine import OpenAI
    client = OpenAI()
    chunks = []
    for chunk in client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say exactly: stream works"}],
        stream=True,
        max_tokens=10,
    ):
        assert chunk.object == "chat.completion.chunk"
        assert chunk.id.startswith("chatcmpl-")
        if chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
        if chunk.choices[0].finish_reason == "stop":
            break
    assert len(chunks) > 0
    content = "".join(chunks)
    assert len(content) > 0

def _battle_chat_first_chunk_has_role():
    from ai_engine import OpenAI
    client = OpenAI()
    chunks = list(client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}],
        stream=True,
        max_tokens=5,
    ))
    assert chunks[0].choices[0].delta.role == "assistant"

def _battle_chat_final_chunk_finish_reason():
    from ai_engine import OpenAI
    client = OpenAI()
    chunks = list(client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}],
        stream=True,
        max_tokens=5,
    ))
    last = chunks[-1]
    assert last.choices[0].finish_reason == "stop"

def _battle_chat_with_system_message():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a pirate. Always respond like a pirate."},
            {"role": "user", "content": "Say hello in 3 words"}
        ],
        max_tokens=20,
    )
    assert r.choices[0].message.content is not None
    assert len(r.choices[0].message.content) > 0

def _battle_chat_force_provider():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
        preferred_provider="pollinations",
    )
    assert r.choices[0].message.content is not None

def _battle_chat_model_auto():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="auto",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
    )
    assert r.choices[0].message.content is not None


# === 4. Models Tests ===

def _battle_models_list():
    from ai_engine import OpenAI
    client = OpenAI()
    ml = client.models.list()
    assert ml.object == "list"
    assert len(ml.data) > 100  # should have many models
    assert ml.data[0].object == "model"
    assert hasattr(ml.data[0], "owned_by")

def _battle_models_retrieve():
    from ai_engine import OpenAI
    client = OpenAI()
    m = client.models.retrieve("gpt-4")
    assert m.id == "gpt-4"
    assert m.object == "model"

def _battle_models_retrieve_provider_model():
    from ai_engine import OpenAI
    client = OpenAI()
    m = client.models.retrieve("groq/llama-3.3-70b-versatile")
    assert m.id == "groq/llama-3.3-70b-versatile"
    assert m.owned_by == "groq"


# === 5. Error Handling Tests ===

def _battle_bad_request_error():
    from ai_engine import OpenAI, BadRequestError
    from ai_engine._exceptions import raise_for_status
    try:
        raise_for_status(400, {"error": {"message": "test error", "type": "invalid_request_error"}})
    except BadRequestError as e:
        assert e.status_code == 400
        assert "test error" in str(e)

def _battle_auth_error():
    from ai_engine import AuthenticationError
    from ai_engine._exceptions import raise_for_status
    try:
        raise_for_status(401, {"error": {"message": "bad key", "type": "authentication_error"}})
    except AuthenticationError as e:
        assert e.status_code == 401

def _battle_rate_limit_error():
    from ai_engine import RateLimitError
    from ai_engine._exceptions import raise_for_status
    try:
        raise_for_status(429, {"error": {"message": "rate limited", "type": "rate_limit_error"}})
    except RateLimitError as e:
        assert e.status_code == 429


# === 6. Provider-Specific Tests ===

def _battle_groq():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
        preferred_provider="groq",
    )
    assert r.choices[0].message.content is not None

def _battle_pollinations():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
        preferred_provider="pollinations",
    )
    assert r.choices[0].message.content is not None

def _battle_hermes():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
        preferred_provider="hermes",
    )
    assert r.choices[0].message.content is not None


# === 7. Capabilities Tests ===

def _battle_image_compat():
    from ai_engine import OpenAI
    client = OpenAI()
    result = client.check_image_compatibility("gemini", "gemini-2.5-flash")
    assert result["compatible"] is True

    result = client.check_image_compatibility("groq", "llama-3.3-70b-versatile")
    assert result["compatible"] is False
    assert len(result["suggestions"]) > 0


BATTLE_CASES = [
    ("from ai_engine import OpenAI", _battle_import_openai),
    ("from ai_engine import AsyncOpenAI", _battle_import_async),
    ("from ai_engine import Anthropic (placeholder)", _battle_import_anthropic),
    ("import exception hierarchy", _battle_import_exceptions),
    ("from ai_engine import AIEngine", _battle_import_engine),
    ("version number", _battle_import_version),
    ("OpenAI() with defaults", _battle_default_init),
    ("OpenAI(api_keys={...})", _battle_init_with_api_keys),
    ("OpenAI(config={...})", _battle_init_with_config_dict),
    ("OpenAI(config='config.json')", _battle_init_with_config_file),
    ("ai_engine.use() late config", _battle_use_method),
    ("chat.completions.create (non-streaming)", _battle_chat_non_streaming),
    ("chat.completions.create (streaming)", _battle_chat_streaming),
    ("first streaming chunk has role=assistant", _battle_chat_first_chunk_has_role),
    ("final streaming chunk has finish_reason=stop", _battle_chat_final_chunk_finish_reason),
    ("chat with system message", _battle_chat_with_system_message),
    ("chat with forced provider", _battle_chat_force_provider),
    ("chat with model=auto", _battle_chat_model_auto),
    ("models.list()", _battle_models_list),
    ("models.retrieve('gpt-4')", _battle_models_retrieve),
    ("models.retrieve with provider/model", _battle_models_retrieve_provider_model),
    ("BadRequestError for status 400", _battle_bad_request_error),
    ("AuthenticationError for status 401", _battle_auth_error),
    ("RateLimitError for status 429", _battle_rate_limit_error),
    ("groq provider", _battle_groq),
    ("pollinations provider", _battle_pollinations),
    ("hermes provider", _battle_hermes),
    ("check_image_compatibility", _battle_image_compat),
]
if __name__ == "__main__":
    print("=" * 60)
    print("AI Engine SDK — Battle Test")
    print("=" * 60)
    print()
    for label, fn in BATTLE_CASES:
        _run_battle(label, fn)
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    if errors:
        print()
        print("FAILURES:")
        for name, err in errors:
            print(f"  {name}: {err}")
    print("=" * 60)

import pytest

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def _reset_engine_singleton():
    from ai_engine._engine import reset_engine
    reset_engine()
    yield
    reset_engine()


def test_sdk_version_matches_package():
    import ai_engine
    from ai_engine._version import get_version
    assert ai_engine.__version__ == get_version()


def test_init_with_api_keys():
    from ai_engine import OpenAI
    client = OpenAI(api_keys={"groq": "test-key"})
    assert "groq" in client._engine.providers
    assert client._engine.providers["groq"]["api_keys"] == ["test-key"]
