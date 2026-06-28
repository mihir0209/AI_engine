#!/usr/bin/env python3
"""Battle test: AI Synapse SDK end-to-end."""
import sys
import os
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0
errors = []

def test(name, func):
    global passed, failed
    try:
        func()
        passed += 1
        print(f"  PASS  {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  FAIL  {name}: {e}")

print("=" * 60)
print("AI Engine SDK — Battle Test")
print("=" * 60)
print()

# === 1. Import Tests ===
print("1. IMPORT TESTS")

def test_import_openai():
    from ai_engine import OpenAI
    assert OpenAI is not None
test("from ai_engine import OpenAI", test_import_openai)

def test_import_async():
    from ai_engine import AsyncOpenAI
    assert AsyncOpenAI is not None
test("from ai_engine import AsyncOpenAI", test_import_async)

def test_import_anthropic():
    from ai_engine import Anthropic
    assert Anthropic is not None
test("from ai_engine import Anthropic (placeholder)", test_import_anthropic)

def test_import_exceptions():
    from ai_engine._exceptions import OpenAIError, BadRequestError, AuthenticationError, RateLimitError, InternalServerError
    assert issubclass(BadRequestError, OpenAIError)
    assert issubclass(AuthenticationError, OpenAIError)
    assert issubclass(RateLimitError, OpenAIError)
    assert issubclass(InternalServerError, OpenAIError)
test("import exception hierarchy", test_import_exceptions)

def test_import_engine():
    from ai_engine import AIEngine
    assert AIEngine is not None
test("from ai_engine import AIEngine", test_import_engine)

def test_import_version():
    import ai_engine
    assert hasattr(ai_engine, "__version__")
    assert ai_engine.__version__ == "4.0.0"
test("version number", test_import_version)

print()

# === 2. Client Initialization Tests ===
print("2. CLIENT INITIALIZATION TESTS")

def test_default_init():
    from ai_engine import OpenAI
    client = OpenAI()
    assert client._engine is not None
    assert len(client._engine.providers) > 0
test("OpenAI() with defaults", test_default_init)

def test_init_with_api_keys():
    from ai_engine import OpenAI
    client = OpenAI(api_keys={"groq": "test-key"})
    assert client._engine.providers["groq"]["api_keys"] == ["test-key"]
test("OpenAI(api_keys={...})", test_init_with_api_keys)

def test_init_with_config_dict():
    from ai_engine import OpenAI
    client = OpenAI(config={"timeout": 60, "default_provider": "groq"})
    assert client._engine is not None
test("OpenAI(config={...})", test_init_with_config_dict)

def test_init_with_config_file():
    from ai_engine import OpenAI
    client = OpenAI(config="ai_engine/config.json")
    assert len(client._engine.providers) > 0
test("OpenAI(config='config.json')", test_init_with_config_file)

def test_use_method():
    import ai_engine
    ai_engine.use(api_keys={"test": "value"})
    assert ai_engine._global_config.get("api_keys", {}).get("test") == "value"
test("ai_engine.use() late config", test_use_method)

print()

# === 3. Chat Completion Tests ===
print("3. CHAT COMPLETION TESTS")

def test_chat_non_streaming():
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
test("chat.completions.create (non-streaming)", test_chat_non_streaming)

def test_chat_streaming():
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
test("chat.completions.create (streaming)", test_chat_streaming)

def test_chat_first_chunk_has_role():
    from ai_engine import OpenAI
    client = OpenAI()
    chunks = list(client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hi"}],
        stream=True,
        max_tokens=5,
    ))
    assert chunks[0].choices[0].delta.role == "assistant"
test("first streaming chunk has role=assistant", test_chat_first_chunk_has_role)

def test_chat_final_chunk_finish_reason():
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
test("final streaming chunk has finish_reason=stop", test_chat_final_chunk_finish_reason)

def test_chat_with_system_message():
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
test("chat with system message", test_chat_with_system_message)

def test_chat_force_provider():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
        preferred_provider="pollinations",
    )
    assert r.choices[0].message.content is not None
test("chat with forced provider", test_chat_force_provider)

def test_chat_model_auto():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="auto",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
    )
    assert r.choices[0].message.content is not None
test("chat with model=auto", test_chat_model_auto)

print()

# === 4. Models Tests ===
print("4. MODELS TESTS")

def test_models_list():
    from ai_engine import OpenAI
    client = OpenAI()
    ml = client.models.list()
    assert ml.object == "list"
    assert len(ml.data) > 100  # should have many models
    assert ml.data[0].object == "model"
    assert hasattr(ml.data[0], "owned_by")
test("models.list()", test_models_list)

def test_models_retrieve():
    from ai_engine import OpenAI
    client = OpenAI()
    m = client.models.retrieve("gpt-4")
    assert m.id == "gpt-4"
    assert m.object == "model"
test("models.retrieve('gpt-4')", test_models_retrieve)

def test_models_retrieve_provider_model():
    from ai_engine import OpenAI
    client = OpenAI()
    m = client.models.retrieve("groq/llama-3.3-70b-versatile")
    assert m.id == "groq/llama-3.3-70b-versatile"
    assert m.owned_by == "groq"
test("models.retrieve with provider/model", test_models_retrieve_provider_model)

print()

# === 5. Error Handling Tests ===
print("5. ERROR HANDLING TESTS")

def test_bad_request_error():
    from ai_engine import OpenAI, BadRequestError
    from ai_engine._exceptions import raise_for_status
    try:
        raise_for_status(400, {"error": {"message": "test error", "type": "invalid_request_error"}})
    except BadRequestError as e:
        assert e.status_code == 400
        assert "test error" in str(e)
test("BadRequestError for status 400", test_bad_request_error)

def test_auth_error():
    from ai_engine import AuthenticationError
    from ai_engine._exceptions import raise_for_status
    try:
        raise_for_status(401, {"error": {"message": "bad key", "type": "authentication_error"}})
    except AuthenticationError as e:
        assert e.status_code == 401
test("AuthenticationError for status 401", test_auth_error)

def test_rate_limit_error():
    from ai_engine import RateLimitError
    from ai_engine._exceptions import raise_for_status
    try:
        raise_for_status(429, {"error": {"message": "rate limited", "type": "rate_limit_error"}})
    except RateLimitError as e:
        assert e.status_code == 429
test("RateLimitError for status 429", test_rate_limit_error)

print()

# === 6. Provider-Specific Tests ===
print("6. PROVIDER-SPECIFIC TESTS")

def test_groq():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
        preferred_provider="groq",
    )
    assert r.choices[0].message.content is not None
test("groq provider", test_groq)

def test_pollinations():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
        preferred_provider="pollinations",
    )
    assert r.choices[0].message.content is not None
test("pollinations provider", test_pollinations)

def test_hermes():
    from ai_engine import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
        preferred_provider="hermes",
    )
    assert r.choices[0].message.content is not None
test("hermes provider", test_hermes)

print()

# === 7. Capabilities Tests ===
print("7. CAPABILITIES TESTS")

def test_image_compat():
    from ai_engine import OpenAI
    client = OpenAI()
    result = client.check_image_compatibility("gemini", "gemini-2.5-flash")
    assert result["compatible"] is True

    result = client.check_image_compatibility("groq", "llama-3.3-70b-versatile")
    assert result["compatible"] is False
    assert len(result["suggestions"]) > 0
test("check_image_compatibility", test_image_compat)

print()

# === Summary ===
print("=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
if errors:
    print()
    print("FAILURES:")
    for name, err in errors:
        print(f"  {name}: {err}")
print("=" * 60)
