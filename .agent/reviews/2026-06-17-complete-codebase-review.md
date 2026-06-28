# Code Review: AI Engine v3.0

**Date:** 2026-06-17  
**Reviewer:** MiMo Code Agent  
**Scope:** Complete codebase review

---

## Project Overview

AI Engine v3.0 is a Python-based multi-provider AI gateway with:
- FastAPI server with OpenAI-compatible API
- 22+ AI provider integrations with intelligent key rotation
- Web dashboard for monitoring and management
- Chat module with SQLite persistence and WebSocket support
- Autodecide feature for automatic provider selection
- Persistent statistics tracking

---

## Critical Issues (Must Fix)

### 1. Duplicate Code in `ai_engine.py`
**Lines:** 86-88, 96-99  
**Issue:** `key_usage_stats`, `key_last_used`, and `key_request_count` are initialized twice in `__init__`.

```python
# Lines 86-88 (first initialization)
self.key_usage_stats = {}
self.key_last_used = {}
self.key_request_count = {}

# Lines 96-99 (duplicate - SHOULD BE REMOVED)
self.key_usage_stats = {}
self.key_last_used = {}
self.key_request_count = {}
```

**Fix:** Remove the duplicate initialization block at lines 96-99.

### 2. Missing `autodecide_cache_timestamps` Attribute
**File:** `ai_engine.py`, line 951  
**Issue:** `self.autodecide_cache_timestamps` is referenced in `_is_cache_valid()` but never initialized in `__init__`.

```python
def _is_cache_valid(self, model_name: str) -> bool:
    if model_name not in self.autodecide_cache_timestamps:  # AttributeError
```

**Fix:** Add `self.autodecide_cache_timestamps = {}` in `__init__` and maintain it during cache operations.

### 3. Unreachable Code in `_select_best_provider`
**File:** `ai_engine.py`, lines 1234-1239  
**Issue:** Code after `return` statement is unreachable.

```python
return best_provider_name, best_model_name  # Line 1233

# Lines 1234-1239 - UNREACHABLE
provider_name, model_name = sorted_providers[0]
if self.verbose:
    verbose_print(f"⚠️ Selected {provider_name} with model '{model_name}' (flagged but best available, self.verbose)")
return provider_name, model_name
```

**Fix:** Remove unreachable code or merge logic before the return.

### 4. SQL Injection Risk in `cleanup_temporary_chats`
**File:** `chat_module/db.py`, lines 277-281  
**Issue:** String formatting used in SQL query construction.

```python
cursor = conn.execute("""
    DELETE FROM chats 
    WHERE is_temporary = 1 
    AND created_at < datetime('now', '-{} hours')
""".format(max_age_hours))  # Potential SQL injection
```

**Fix:** Use parameterized queries: `datetime('now', ? || ' hours')` with `(str(max_age_hours),)`.

### 5. Error Message String Formatting Bug
**File:** `ai_engine.py`, lines 1445, 2181  
**Issue:** `str()` called with wrong argument count.

```python
verbose_print(f"💥 {provider_name} exception: {str(e, self.verbose)}")
#                                          ^^^^^^^^^^^^^^^^^^
# str() only takes 1 argument, this will raise TypeError
```

**Fix:** Change to `str(e)` and handle verbose separately.

---

## High Priority Issues

### 6. Thread Safety Concerns
**File:** `ai_engine.py`  
**Issue:** Shared mutable state (`flagged_keys`, `usage_stats`, `key_usage_stats`) accessed without locks in multi-threaded server environment.

**Recommendation:** Add threading locks for shared state mutations or use thread-safe data structures.

### 7. Blocking I/O in Async Context
**File:** `server.py`, line 238  
**Issue:** `engine.chat_completion()` uses synchronous `requests` library in async endpoint.

```python
result = engine.chat_completion(...)  # Blocks the event loop
```

**Current Mitigation:** Chat module uses `asyncio.to_thread()`, but `/v1/chat/completions` endpoint does not.

**Fix:** Wrap in `await asyncio.to_thread(engine.chat_completion, ...)`.

### 8. Error Handling Silently Swallows Exceptions
**File:** `statistics_manager.py`, lines 61-63  
**Issue:** Bare `except` clause hides deserialization errors.

```python
except:
    data['last_used'] = None
```

**Fix:** Use `except (ValueError, TypeError):` to catch specific exceptions.

### 9. Missing Error Handling for `stats_manager` None
**File:** `ai_engine.py`, line 132  
**Issue:** When `StatisticsManager` import fails, `get_stats_manager` returns `None`, but line 132 calls `.get_statistics()` on it.

```python
persistent_key_stats = self.stats_manager.get_statistics(provider_name, key_id)
# AttributeError if stats_manager is None
```

**Fix:** Add null check: `if self.stats_manager:` before calling methods.

### 10. Model Cache Format Inconsistency
**File:** `server.py`, lines 354, 366  
**Issue:** Mixed use of `/` and `|` separators in model ID format.

```python
# Line 316 uses | separator
all_models.append(f"{provider_name}|{model}")

# Line 354 uses / separator (inconsistent)
all_models.append(f"{provider_name}/{current_model}")
```

**Fix:** Standardize on `|` separator throughout.

---

## Medium Priority Issues

### 11. Config File Modified at Runtime
**File:** `server.py`, `save_config_to_file()`  
**Issue:** `config.py` is modified during runtime via API calls. This is fragile and can cause issues with:
- File locking conflicts
- Race conditions in multi-worker deployments
- Config changes lost on restart if not properly saved

**Recommendation:** Use a separate JSON config file for runtime changes.

### 12. CORS Configuration Too Permissive
**File:** `server.py`, lines 120-126  
**Issue:** `allow_origins=["*"]` is insecure for production.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Security risk in production
```

**Fix:** Configure specific origins or use environment variable.

### 13. No Rate Limiting on API Endpoints
**Issue:** No rate limiting middleware on FastAPI endpoints, allowing potential abuse.

**Recommendation:** Add rate limiting middleware (e.g., `slowapi`).

### 14. Token Estimation is Inaccurate
**File:** `server.py`, lines 189-191  
**Issue:** Token count estimation is rough and inaccurate.

```python
prompt_tokens = max(1, len(prompt_text.split()) + len(prompt_text) // 4)
```

**Recommendation:** Use tiktoken or similar for accurate counting, or return null and let clients calculate.

### 15. WebSocket Memory Leak Potential
**File:** `chat_module/websocket_manager.py`  
**Issue:** If clients disconnect without proper WebSocket close, connections may accumulate.

**Recommendation:** Add heartbeat/ping mechanism and connection timeout.

---

## Low Priority Issues / Code Quality

### 16. Inconsistent Naming Conventions
- `AI_engine` class uses underscore (should be `AIEngine` per PEP 8)
- `AI_CONFIGS`, `ENGINE_SETTINGS` are module-level constants (correct)
- Mixed use of `verbose_print` vs direct `print` statements

### 17. Missing Type Hints in Some Areas
- `_make_request` and related methods lack complete type annotations
- Some `Dict` usages should use more specific types

### 18. Logging Inconsistency
- Mix of `logging` module and `print()` statements
- `verbose_print` function used inconsistently

### 19. Documentation Gaps
- No docstrings on some public methods
- API endpoint documentation could be more detailed

### 20. Test Coverage
- No test files found in the repository
- No testing framework configured

### 21. Unused Imports
- `aiohttp` imported in `server.py` but only used in one async function
- Various unused imports scattered throughout

---

## Architecture Observations

### Strengths
1. **Multi-provider resilience** - Smart rotation and fallback logic is well-designed
2. **Persistent statistics** - Key usage tracking across restarts is valuable
3. **Autodecide feature** - Automatic provider selection based on model availability
4. **Modular design** - Clean separation between engine, server, and chat module
5. **Comprehensive error classification** - Good categorization of different failure types

### Concerns
1. **Configuration complexity** - 22 providers with similar configs suggest need for abstraction
2. **State management** - Heavy reliance on in-memory state that doesn't survive restarts
3. **Scalability** - SQLite may become bottleneck under high load
4. **Monitoring** - Limited observability beyond basic statistics

---

## Recommendations Summary

| Priority | Count | Action |
|----------|-------|--------|
| Critical | 5 | Fix immediately - bugs affecting correctness |
| High | 5 | Fix soon - reliability and security concerns |
| Medium | 5 | Plan to fix - improvements for production readiness |
| Low | 6 | Nice to have - code quality improvements |

---

## Files Reviewed

| File | Lines | Key Findings |
|------|-------|--------------|
| `ai_engine.py` | 2200+ | Duplicate code, unreachable code, missing attributes |
| `server.py` | 1242 | CORS, blocking I/O, config mutation |
| `config.py` | 650 | Well-structured, no major issues |
| `model_cache.py` | 202 | Thread-safe, well-designed |
| `statistics_manager.py` | 253 | Missing null checks, bare except |
| `chat_module/router.py` | 663 | Good async handling, some edge cases |
| `chat_module/db.py` | 303 | SQL injection risk, good migrations |
| `chat_module/websocket_manager.py` | 121 | Clean, potential memory leak |

---

*Review completed: 2026-06-17*
