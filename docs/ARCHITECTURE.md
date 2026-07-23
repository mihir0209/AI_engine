# AI Synapse — Architecture

## Canonical code layout (single source of truth)

| Concern | Canonical module | Legacy shim (repo root) |
|---------|------------------|-------------------------|
| HTTP server + dashboard | `ai_engine/server/app.py` | `server.py` → re-exports `app`, `main` |
| Chat REST + WebSocket | `ai_engine/server/chat_module/` | `chat_module/` → re-exports |
| Provider config | `core/config.py` | `config.py` → re-exports |
| Intent routing | `core/intent_classifier.py` | — |
| CLI server | `python -m ai_engine serve` | `OpenAI().serve()` → packaged `app` |
| TUI chat / image gen | `core.ai_engine` via `ai_engine/tui/routing_engine.py` | Same engine as server chat |
| Provider observability | `core/provider_observability.py` | Dashboard consumes normalized snapshots |

The TUI execution seam exposes `chat_completion()` for a `RequestResult` and
`stream_chat_completion()` for normalized dictionaries (`content`, `done`,
`provider`, `model`, or `error`). OpenAI SDK response objects remain inside
`ai_engine/resources/chat.py`; they are not part of the TUI contract.

Provider-facing dashboard views use `core.provider_observability` as a read-only
composition seam. It normalizes health, latency, rate-limit, usage, and existing
circuit-breaker state without creating provider state or making network calls.

PyPI ships `ai_engine*` and `core*` only. Root shims exist for editable installs and older docs.

---

## How Every Feature Works

### 1. Import & Initialization

```
from ai_engine import OpenAI
client = OpenAI()
```

**What happens:**
1. `OpenAI.__init__()` calls `_resolve_config()` which loads:
   - `ai_engine/config.json` (provider priorities, CDN settings)
   - Constructor args (`api_keys`, `config`, etc.)
   - Environment variables (`AI_ENGINE_API_KEY_*`)
2. `_init_engine(config)` applies config.json overrides to `core.config.AI_CONFIGS`
3. Creates `AI_engine` instance which loads 26 enabled providers from `core.config.AI_CONFIGS`
4. Engine is cached as singleton via `get_engine()` — all clients share it

**No server involved. Everything runs in-process.**

### 2. Chat Completion Flow

```
client.chat.completions.create(model="gpt-4", messages=[...])
```

**What happens:**
1. `OpenAI.chat.completions.create()` calls `engine.chat_completion()`
2. Engine calls `_get_available_providers()` — filters by health monitor + rate limits
3. For each available provider (in priority order):
   a. `_request_with_key_rotation()` (forced provider, preferred provider, and default fallback paths) retries across valid API keys on 401/429/quota errors; `_make_request()` dispatches to format-specific handler:
      - `openai` format → POST with Bearer auth
      - `gemini` format → POST with `?key=` parameter
      - `cohere` format → POST with Authorization header
      - `cloudflare` format → POST to `/run/{model}` path
      - `a3z_get` format → GET with `?message=` parameter
   b. If success: returns `RequestResult(content=..., provider_used=...)`
   c. If fail: tries next provider (auto-failover)
4. SDK wraps `RequestResult` into `ChatCompletion` object (OpenAI-compatible format)

**All HTTP calls go directly to provider APIs from the SDK. No server in the middle.**

### 3. Model Discovery

```
client.models.list()  # Returns 1100+ models
```

**What happens:**
1. Checks `shared_model_cache` for cached models
2. If cache is empty (first call): triggers `_discover_and_cache_models_sync()`
3. This method:
   a. Finds all enabled providers with `model_endpoint` configured (23 providers)
   b. Uses `ThreadPoolExecutor` to fetch `GET /v1/models` from each provider simultaneously
   c. Each fetch is a direct HTTP request to the provider's API
   d. Results saved to `shared_model_cache` (JSON file with 30-min TTL)
4. Returns cached models as `ModelList` object

**The discovery makes HTTP requests directly to provider APIs from the SDK.**

### 4. Streaming

```
for chunk in client.chat.completions.create(model="gpt-4", messages=[...], stream=True):
    print(chunk.choices[0].delta.content)
```

**What happens:**
1. SDK calls `engine.chat_completion()` (non-streaming) to get the full response
2. SDK simulates streaming by sending word-by-word chunks
3. Each chunk follows OpenAI's SSE format:
   - First chunk: `delta={"role": "assistant"}`
   - Content chunks: `delta={"content": "..."}`
   - Final chunk: `delta={}`, `finish_reason="stop"`

**This is the standard approach for OpenAI-compatible proxies. The upstream providers may or may not support real SSE — the SDK handles both.**

### 5. Vision Capability Detection

```
result = client.check_image_compatibility("groq", "llama-3.3-70b")
# {"compatible": false, "reason": "...", "suggestions": ["gemini", "openrouter"]}
```

**What happens:**
1. Reads from `core.capabilities.capability_manager`
2. Checks model-level database (32 known models across 10 providers)
3. Falls back to provider-level capabilities if model not in database
4. Returns compatibility result with suggested alternatives

**Pure in-memory lookup. No network calls.**

### 6. Config Reload

```
client.refresh_config()
```

**What happens:**
1. Deletes `data/cdn_config_cache.py` and `data/cdn_config_meta.json`
2. Triggers `config_fetcher.fetch_and_apply()` from CDN
3. Re-applies overrides to `AI_CONFIGS`

**Requires network access to jsDelivr CDN.**

### 7. Server Mode

```
client.serve(port=8000)
```

**What happens:**
1. Imports `server.app` (FastAPI)
2. Starts `uvicorn` with the app
3. Provides web dashboard, chat UI, REST API, Swagger docs

**This is optional — the SDK works without the server.**

## Provider Routing Priority

Providers are tried in priority order (lower = higher priority):

| Priority | Provider | Auth | Free |
|----------|----------|------|------|
| 1 | mimo | API key | Yes |
| 2 | groq | API key | Free tier |
| 2 | hcnsec | API key | Custom |
| 2 | llm7 | API key | Custom |
| 2 | pollinations | None | Yes |
| 3 | openrouter | API key | Free tier |
| 3 | github | API key | Free tier |
| 3 | paxsenix | None | Custom |
| 3 | g4f_groq | None | Yes (g4f.space) |
| 4 | gemini | API key | Free tier |
| 4 | g4f_gemini | None | Yes (g4f.space) |
| 5 | cerebras | API key | Free tier |
| 5 | g4f_pollinations | None | Yes (g4f.space) |
| 6 | zai | API key | Free tier |
| 7 | hermes | None | Yes |
| 14 | opencode_zen | None | Yes |
| 15 | kilo | API key | Free tier |

## Data Flow Diagram

```
Developer Code
    │
    ▼
ai_engine.OpenAI() ──── _resolve_config() ──→ config.json + env vars
    │
    ▼
ai_engine._engine._init_engine() ──→ core.config.AI_CONFIGS (overrides applied)
    │
    ▼
core.ai_engine.AI_engine() ──→ loads providers from AI_CONFIGS
    │
    ▼
client.chat.completions.create()
    │
    ▼
engine.chat_completion()
    │
    ├─→ _get_available_providers() ──→ health_monitor + rate_limit_manager
    │
    ├─→ _make_request(provider, config, messages) ──→ provider_requests.py
    │       │
    │       ├─→ _make_openai_request() ──→ requests.post(endpoint, ...)
    │       ├─→ _make_gemini_request() ──→ requests.post(endpoint?key=..., ...)
    │       ├─→ _make_cohere_request()  ──→ requests.post(endpoint, ...)
    │       └─→ _make_cloudflare_request() ──→ requests.post(endpoint/run/model, ...)
    │
    ▼
RequestResult(success, content, provider_used, model_used)
    │
    ▼
ChatCompletion(id, object, model, choices, usage)  ← SDK wraps result
```

## Package Structure

```
ai_engine/              # SDK package (PyPI: ai-synapse)
├── __init__.py         # from ai_engine import OpenAI
├── openai.py           # OpenAI, AsyncOpenAI — drop-in replacements
├── anthropic.py        # Anthropic, AsyncAnthropic — drop-in replacements
├── _engine.py          # Shared engine singleton + config
├── _exceptions.py      # Error hierarchy
├── config.json         # Provider priorities
├── resources/
│   ├── chat.py         # Completions, AsyncCompletions
│   └── models.py       # Models, AsyncModels
└── types/
    └── __init__.py     # ChatCompletion, Model, etc.

core/                   # Engine modules (imported by SDK)
├── ai_engine.py        # AI_engine class
├── cli.py              # CLI interface (extracted from ai_engine.py)
├── provider_requests.py # HTTP request methods (OpenAI, Anthropic, Gemini, Bedrock, Vertex AI, etc.)
├── config.py           # Provider configs (29 providers, 12 formats)
├── config_sync.py      # CDN config sync with caching
├── infrastructure.py   # Circuit breakers, retry logic, health checks
├── capabilities.py     # Vision/tool detection
├── health_monitor.py   # Provider health tracking
├── rate_limit_manager.py # Rate limiting
├── model_cache.py      # Model cache with TTL
├── latency_tracker.py  # Latency tracking
└── usage_tracker.py    # Usage tracking

monitoring/             # Observability configs
├── grafana/            # Grafana dashboards
└── prometheus-alerts.yml # Alerting rules
```
```
