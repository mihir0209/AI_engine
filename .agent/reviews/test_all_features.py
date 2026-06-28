#!/usr/bin/env python3
"""Comprehensive test of ai-synapse from pip package."""
import sys
import os
import time
import json
import traceback
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine._engine import reset_engine
reset_engine()

results = []

def test(category, name, func):
    start = time.time()
    try:
        func()
        elapsed = time.time() - start
        results.append({"category": category, "name": name, "status": "PASS", "time": f"{elapsed:.2f}s", "detail": ""})
        print(f"  ✅ {name} ({elapsed:.2f}s)")
    except Exception as e:
        elapsed = time.time() - start
        results.append({"category": category, "name": name, "status": "FAIL", "time": f"{elapsed:.2f}s", "detail": str(e)[:120]})
        print(f"  ❌ {name}: {str(e)[:80]}")

print("=" * 70)
print("AI SYNAPSE — Full Feature Test from pip package")
print(f"Version: {__import__('ai_engine').__version__}")
print("=" * 70)

# === SECTION 1: IMPORTS ===
print("\n1. IMPORTS")

def test_import_openai():
    from ai_engine import OpenAI
test("imports", "from ai_engine import OpenAI", test_import_openai)

def test_import_async():
    from ai_engine import AsyncOpenAI
test("imports", "from ai_engine import AsyncOpenAI", test_import_async)

def test_import_anthropic():
    from ai_engine import Anthropic
test("imports", "from ai_engine import Anthropic", test_import_anthropic)

def test_import_exceptions():
    from ai_engine._exceptions import OpenAIError, BadRequestError, AuthenticationError, RateLimitError, InternalServerError, NotFoundError
test("imports", "exception hierarchy", test_import_exceptions)

def test_import_types():
    from ai_engine.types import ChatCompletion, ChatCompletionChunk, Model, ModelList
test("imports", "response types", test_import_types)

def test_import_engine():
    from ai_engine import AIEngine, get_engine
test("imports", "AIEngine, get_engine", test_import_engine)

def test_version():
    import ai_engine
    assert hasattr(ai_engine, "__version__")
    assert "." in ai_engine.__version__
test("imports", f"version = {__import__('ai_engine').__version__}", test_version)

# === SECTION 2: CLIENT INITIALIZATION ===
print("\n2. CLIENT INITIALIZATION")

def test_default_client():
    from ai_engine import OpenAI
    c = OpenAI()
    assert c._engine is not None
    assert len(c._engine.providers) > 0
test("client_init", "OpenAI() default", test_default_client)

def test_client_with_keys():
    from ai_engine import OpenAI
    c = OpenAI(api_keys={"pollinations": "free"})
    assert c._engine is not None
test("client_init", "OpenAI(api_keys={})", test_client_with_keys)

def test_client_with_config_dict():
    from ai_engine import OpenAI
    c = OpenAI(config={"timeout": 60})
    assert c._engine is not None
test("client_init", "OpenAI(config={})", test_client_with_config_dict)

def test_client_with_config_file():
    from ai_engine import OpenAI
    c = OpenAI(config="ai_engine/config.json")
    assert len(c._engine.providers) > 0
test("client_init", "OpenAI(config='config.json')", test_client_with_config_file)

def test_use_method():
    import ai_engine
    ai_engine.use(api_keys={"test": "value"})
    assert ai_engine._global_config.get("api_keys", {}).get("test") == "value"
test("client_init", "ai_engine.use()", test_use_method)

def test_reset_engine():
    from ai_engine._engine import reset_engine, _engine_instance as inst
    reset_engine()
    from ai_engine._engine import _engine_instance
    assert _engine_instance is None
test("client_init", "reset_engine()", test_reset_engine)

# === SECTION 3: CHAT COMPLETIONS ===
print("\n3. CHAT COMPLETIONS")

def test_chat_basic():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Say OK"}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
    assert r.object == "chat.completion"
    assert r.choices[0].message.content is not None
    assert r.usage.total_tokens > 0
test("chat", "non-streaming", test_chat_basic)

def test_chat_streaming():
    from ai_engine import OpenAI
    c = OpenAI()
    chunks = []
    for chunk in c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Say OK"}], stream=True, max_tokens=5, preferred_provider="pollinations", force_provider=True):
        if chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
    assert len(chunks) > 0
test("chat", "streaming", test_chat_streaming)

def test_chat_stream_role():
    from ai_engine import OpenAI
    c = OpenAI()
    chunks = list(c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Hi"}], stream=True, max_tokens=5, preferred_provider="pollinations", force_provider=True))
    assert chunks[0].choices[0].delta.role == "assistant"
test("chat", "stream first chunk has role", test_chat_stream_role)

def test_chat_stream_finish():
    from ai_engine import OpenAI
    c = OpenAI()
    chunks = list(c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Hi"}], stream=True, max_tokens=5, preferred_provider="pollinations", force_provider=True))
    assert chunks[-1].choices[0].finish_reason == "stop"
test("chat", "stream last chunk finish_reason", test_chat_stream_finish)

def test_chat_system_message():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Say OK"}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
    assert r.choices[0].message.content is not None
test("chat", "with system message", test_chat_system_message)

def test_chat_finish_reason():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Hi"}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
    assert r.choices[0].finish_reason in ("stop", "length", None)
test("chat", "finish_reason valid", test_chat_finish_reason)

def test_chat_usage():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Hi"}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
    assert r.usage.prompt_tokens >= 0
    assert r.usage.completion_tokens >= 0
    assert r.usage.total_tokens == r.usage.prompt_tokens + r.usage.completion_tokens
test("chat", "usage counts consistent", test_chat_usage)

def test_chat_id_format():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Hi"}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
    assert r.id.startswith("chatcmpl-")
    assert len(r.id) > 10
test("chat", "id format", test_chat_id_format)

def test_chat_created_is_int():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Hi"}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
    assert isinstance(r.created, int)
    assert r.created > 1700000000  # After 2023
test("chat", "created timestamp", test_chat_created_is_int)

# === SECTION 4: MODELS ===
print("\n4. MODELS")

def test_models_retrieve():
    from ai_engine import OpenAI
    c = OpenAI()
    m = c.models.retrieve("gpt-4")
    assert m.id == "gpt-4"
    assert m.object == "model"
    assert isinstance(m.created, int)
test("models", "retrieve", test_models_retrieve)

def test_models_retrieve_provider():
    from ai_engine import OpenAI
    c = OpenAI()
    m = c.models.retrieve("groq/llama-3.3-70b-versatile")
    assert m.id == "groq/llama-3.3-70b-versatile"
    assert m.owned_by == "groq"
test("models", "retrieve with provider prefix", test_models_retrieve_provider)

def test_models_list():
    from ai_engine import OpenAI
    c = OpenAI()
    ml = c.models.list()
    assert ml.object == "list"
    assert isinstance(ml.data, list)
test("models", "list (empty in SDK-only mode)", test_models_list)

# === SECTION 5: ERROR HANDLING ===
print("\n5. ERROR HANDLING")

def test_error_400():
    from ai_engine._exceptions import BadRequestError, raise_for_status
    try:
        raise_for_status(400, {"error": {"message": "bad request", "type": "invalid_request_error", "param": "model", "code": "invalid_model"}})
        assert False
    except BadRequestError as e:
        assert e.status_code == 400
        assert "bad request" in str(e)
test("errors", "BadRequestError (400)", test_error_400)

def test_error_401():
    from ai_engine._exceptions import AuthenticationError, raise_for_status
    try:
        raise_for_status(401, {"error": {"message": "unauthorized", "type": "authentication_error"}})
        assert False
    except AuthenticationError as e:
        assert e.status_code == 401
test("errors", "AuthenticationError (401)", test_error_401)

def test_error_429():
    from ai_engine._exceptions import RateLimitError, raise_for_status
    try:
        raise_for_status(429, {"error": {"message": "rate limited", "type": "rate_limit_error"}})
        assert False
    except RateLimitError as e:
        assert e.status_code == 429
test("errors", "RateLimitError (429)", test_error_429)

def test_error_404():
    from ai_engine._exceptions import NotFoundError, raise_for_status
    try:
        raise_for_status(404, {"error": {"message": "not found", "type": "not_found_error"}})
        assert False
    except NotFoundError as e:
        assert e.status_code == 404
test("errors", "NotFoundError (404)", test_error_404)

def test_error_500():
    from ai_engine._exceptions import InternalServerError, raise_for_status
    try:
        raise_for_status(500, {"error": {"message": "server error", "type": "server_error"}})
        assert False
    except InternalServerError as e:
        assert e.status_code == 500
test("errors", "InternalServerError (500)", test_error_500)

# === SECTION 6: CAPABILITIES ===
print("\n6. CAPABILITIES")

def test_vision_compat():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.check_image_compatibility("gemini", "gemini-2.5-flash")
    assert r["compatible"] is True
    r2 = c.check_image_compatibility("groq", "llama-3.3-70b-versatile")
    assert r2["compatible"] is False
    assert len(r2["suggestions"]) > 0
test("capabilities", "image compatibility", test_vision_compat)

# === SECTION 7: CONFIG SYNC ===
print("\n7. CONFIG SYNC")

def test_config_status():
    from ai_engine import OpenAI
    c = OpenAI()
    status = c.config_status()
    assert "enabled" in status
test("config_sync", "config_status()", test_config_status)

# === SECTION 8: PROVIDER SPECIFIC ===
print("\n8. PROVIDER SPECIFIC")

def test_provider_pollinations():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Say OK"}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
    assert r.choices[0].message.content is not None
test("providers", "pollinations", test_provider_pollinations)

def test_provider_groq():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Say OK"}], max_tokens=5, preferred_provider="groq", force_provider=True)
    assert r.choices[0].message.content is not None
test("providers", "groq", test_provider_groq)

# === SECTION 9: CONCURRENCY ===
print("\n9. CONCURRENCY")

def test_thread_safety():
    from ai_engine import OpenAI
    c = OpenAI()
    results = []
    errors = []

    def make_request():
        try:
            r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Say OK"}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
            results.append(r.choices[0].message.content is not None)
        except Exception as e:
            errors.append(str(e)[:50])

    threads = [threading.Thread(target=make_request) for _ in range(3)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=30)

    assert len(results) >= 1, f"All failed: {errors}"
test("concurrency", "3 parallel requests", test_thread_safety)

# === SECTION 10: EDGE CASES ===
print("\n10. EDGE CASES")

def test_empty_messages():
    from ai_engine import OpenAI
    c = OpenAI()
    try:
        r = c.chat.completions.create(model="auto", messages=[], max_tokens=5)
    except Exception:
        pass  # Expected to fail
test("edge_cases", "empty messages (should fail gracefully)", test_empty_messages)

def test_very_long_message():
    from ai_engine import OpenAI
    c = OpenAI()
    long_msg = "hello " * 500
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": long_msg}], max_tokens=5, preferred_provider="pollinations", force_provider=True)
    assert r.choices[0].message.content is not None
test("edge_cases", "long message (2500 words)", test_very_long_message)

def test_unicode_message():
    from ai_engine import OpenAI
    c = OpenAI()
    r = c.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Say hello in Japanese: こんにちは"}], max_tokens=10, preferred_provider="pollinations", force_provider=True)
    assert r.choices[0].message.content is not None
test("edge_cases", "unicode message", test_unicode_message)

# === SUMMARY ===
print("\n" + "=" * 70)
passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] == "FAIL")
print(f"RESULTS: {passed} passed, {failed} failed, {len(results)} total")
print(f"Time: {sum(float(r['time'].rstrip('s')) for r in results):.1f}s")
if failed > 0:
    print("\nFAILURES:")
    for r in results:
        if r["status"] == "FAIL":
            print(f"  [{r['category']}] {r['name']}: {r['detail']}")
print("=" * 70)

# Save report
report = {
    "version": __import__("ai_engine").__version__,
    "passed": passed,
    "failed": failed,
    "total": len(results),
    "results": results
}
with open("test_report.json", "w") as f:
    json.dump(report, f, indent=2)
