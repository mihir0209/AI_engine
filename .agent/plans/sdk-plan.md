# AI Engine SDK Plan (v2)

## Vision

Drop-in replacements for provider SDKs. Same class names, same API, but with AI Engine's free provider routing underneath.

```python
# BEFORE: pay per provider
from openai import OpenAI
client = OpenAI(api_key="sk-expensive")  # one provider, one key

# AFTER: free multi-provider routing
from ai_engine import OpenAI
client = AIEngine(api_key="dummy")       # routes through 27 free providers
client.chat.completions.create(model="gpt-4", messages=[...])
```

```python
# Anthropic support (future)
from ai_engine import Anthropic
client = Anthropic(api_key="dummy")
client.messages.create(model="claude-3-haiku", max_tokens=100, messages=[...])
```

**Same class names. Same methods. Same response types.** Developers swap one import line and get free multi-provider routing.

## Why This Design

1. **Zero learning curve** — Developers already know `openai.OpenAI` and `anthropic.Anthropic`
2. **Future-proof** — Adding Anthropic is just adding another resource class
3. **SDK-native** — No HTTP server, no Docker, no ports. Pure Python library
4. **CDN-powered** — Always has the latest providers via jsDelivr CDN sync
5. **One dependency** — Just `pip install ai-engine`

## Architecture

### The Core Insight

Each provider SDK (OpenAI, Anthropic) is just a thin HTTP client that sends requests to an API. AI Engine already knows how to:
- Route requests to the right provider
- Handle failover between providers
- Rotate API keys
- Format responses in OpenAI/Anthropic format

The SDK just needs to be a **proxy class** that intercepts SDK calls and routes them through AI Engine's core.

### What Reuses Existing Code (No Duplication)

| Component | Source | Reused As |
|-----------|--------|-----------|
| AI_engine class | `core/ai_engine.py` | Engine backbone |
| Provider requests | `core/provider_requests.py` | HTTP transport |
| Health monitoring | `core/health_monitor.py` | Failover logic |
| Rate limiting | `core/rate_limit_manager.py` | Request throttling |
| Capabilities | `core/capabilities.py` | Vision/model detection |
| CDN sync | `core/config_sync.py` | Provider config sync |
| Model cache | `core/model_cache.py` | Model discovery |
| Config | `config.py` | Provider definitions |

### What's New (SDK Layer — ~400 lines total)

```
ai_engine/
├── __init__.py          # from ai_engine import OpenAI, Anthropic, AIEngine
├── openai.py            # OpenAI class (drop-in replacement)
├── anthropic.py         # Anthropic class (future)
├── _engine.py           # Shared engine singleton
├── _exceptions.py       # Error classes (OpenAIError, AnthropicError)
├── _streaming.py        # Stream/AsyncStream classes
├── _types.py            # Shared types
└── py.typed
```

## SDK API Design

### OpenAI Compatibility

```python
from ai_engine import OpenAI

client = OpenAI(api_key="dummy")  # any key works, SDK routes through free providers

# Non-streaming
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
# Returns standard OpenAI ChatCompletion object

# Streaming
for chunk in client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True
):
    print(chunk.choices[0].delta.content, end="")

# Models
models = client.models.list()
model = client.models.retrieve("gpt-4")
```

### Anthropic Compatibility (future)

```python
from ai_engine import Anthropic

client = Anthropic(api_key="dummy")

response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.content[0].text)
```

### AIEngine (advanced — for provider-specific features)

```python
from ai_engine import AIEngine

client = AIEngine(api_keys={"groq": "gsk_...", "gemini": "AI..."})

# AI Engine-specific features
response = client.chat.completions.create(
    model="groq/llama-3.3-70b-versatile",  # force specific provider
    messages=[{"role": "user", "content": "Hello!"}]
)

# Check which providers support an image
compat = client.check_image_compatibility("groq", "llama-3.3-70b-versatile")
# {"compatible": false, "suggestions": ["gemini", "openrouter"]}
```

### Configuration

The SDK ships with a `config.json` at the package root that users can override. This is the primary configuration surface — providers, priorities, API keys, CDN, everything in one place.

#### config.json (ships with package, user-editable)

```json
{
    "cdn_config_url": "default",
    "cdn_config_ttl": 86400,
    "default_provider": null,
    "timeout": 30,
    "max_retries": 2,
    "api_keys": {},
    "providers": {
        "groq": {"priority": 2, "enabled": true},
        "gemini": {"priority": 5, "enabled": true},
        "openrouter": {"priority": 3, "enabled": true},
        "g4f": {"enabled": false},
        "ollama": {"enabled": false},
        "zai": {"priority": 6, "enabled": true},
        "hcnsec": {"priority": 2, "enabled": true},
        "mimo": {"priority": 1, "enabled": true},
        "paxsenix": {"priority": 3, "enabled": true},
        "llm7": {"priority": 2, "enabled": true},
        "kilo": {"priority": 15, "enabled": true},
        "opencode_zen": {"priority": 14, "enabled": true}
    }
}
```

Users edit this file to control which providers are used, their priorities, and API keys. The SDK reads this on initialization and merges with any constructor/env overrides.

#### Constructor args (override config.json)

```python
# Minimal (reads config.json + env vars)
client = OpenAI()

# Override specific settings
client = OpenAI(api_keys={"groq": "gsk_...", "gemini": "AI..."})
client = OpenAI(config={"timeout": 60, "default_provider": "groq"})

# Use a different config file
client = OpenAI(config="my_config.json")
```

#### Environment variables (override config.json)

```bash
AI_ENGINE_API_KEY_GROQ=gsk_...
AI_ENGINE_API_KEY_GEMINI=AI...
AI_ENGINE_CDN_CONFIG=default
AI_ENGINE_TIMEOUT=30
```

```python
client = OpenAI()  # reads config.json + env vars
```

#### Late configuration via use()

```python
import ai_engine

ai_engine.use(
    api_keys={"groq": "gsk_..."},
    cdn_config="default"
)

client = ai_engine.OpenAI()  # uses global config
```

### Async Support

```python
from ai_engine import AsyncOpenAI

async def main():
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print(response.choices[0].message.content)
```

### CDN Config Sync

```python
# SDK auto-fetches latest provider configs from jsDelivr
client = OpenAI(cdn_config="default")

# Or custom CDN URL
client = OpenAI(cdn_config="https://raw.githubusercontent.com/you/repo/main/config.py")

# Disable CDN (use local config only)
client = OpenAI(cdn_config="")
```

## Implementation Details

### OpenAI class (`ai_engine/openai.py`)

```python
class OpenAI:
    """Drop-in replacement for openai.OpenAI"""
    
    def __init__(self, *, api_key="dummy", base_url=None, config=None,
                 cdn_config=None, timeout=30, **kwargs):
        # 1. Load config from: config arg → env vars → defaults
        # 2. Initialize AI_engine with merged config
        # 3. Set up chat.completions, models resources
    
    @property
    def chat(self):
        return _Chat(self._engine)
    
    @property
    def models(self):
        return _Models(self._engine)
```

### Chat.Completions resource

```python
class _ChatCompletions:
    def create(self, *, model, messages, stream=False, **kwargs):
        # 1. Call engine.chat_completion() or engine.chat_completion_stream()
        # 2. Convert RequestResult to ChatCompletion or Stream
        # 3. Return standard OpenAI-format response object
```

### Response types

```python
class ChatCompletion:     # Matches openai.types.chat.ChatCompletion
    id: str               # "chatcmpl-..."
    object: str           # "chat.completion"
    created: int          # Unix timestamp
    model: str            # Model name
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage

class ChatCompletionChunk:  # For streaming
    id: str
    object: str           # "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]
```

## Implementation Steps

### Step 1: Repo reorganization (30 min)
- Create `ai_engine/` package directory at root
- Move server components: `server.py` → `server/app.py`, `chat_module/` → `server/chat_module/`
- Move `templates/`, `static/` → `server/`
- Keep `core/`, `config.py` at root (shared by SDK + server)
- Update server imports to use new paths

### Step 2: SDK skeleton (30 min)
- `ai_engine/__init__.py` — exports OpenAI, Anthropic (placeholder), AIEngine
- `ai_engine/_engine.py` — shared engine singleton with CDN config
- `ai_engine/_exceptions.py` — OpenAIError, AnthropicError, etc.
- `ai_engine/_types.py` — NotGiven, Timeout helpers
- `ai_engine/py.typed`

### Step 3: OpenAI drop-in class (1 hr)
- `ai_engine/openai.py` — `OpenAI` class + `_Chat`, `_ChatCompletions`, `_Models`
- Response types matching OpenAI SDK format
- Streaming support via `chat_completion_stream()`
- Error mapping from `RequestResult` to SDK exceptions
- AsyncOpenAI placeholder

### Step 4: Configuration system (30 min)
- JSON config loading
- Constructor arg merging with env vars
- CDN sync integration
- `ai_engine.use()` for late config
- `AIEngine` class with AI Engine-specific features

### Step 5: Tests (30 min)
- `tests/test_sdk_openai.py` — verify `from ai_engine import OpenAI` works
- Verify response format matches OpenAI SDK exactly
- Verify streaming works
- Verify with actual providers
- Verify Anthropic stub returns proper error

### Step 6: Documentation + release (30 min)
- Update README.md: SDK-first, server-second
- SDK quickstart with config.json example
- Provider setup guide (which keys to get)
- Tag v4.0.0

## Migration

### Existing server users (no change needed)
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")
# Still works — server is still available
```

### New SDK users
```python
from ai_engine import OpenAI
client = OpenAI()
# No server, no Docker, just pip install ai-engine
```

### Future: Anthropic migration
```python
# Before
from anthropic import Anthropic
client = Anthropic(api_key="sk-expensive")

# After
from ai_engine import Anthropic
client = Anthropic(api_key="dummy")  # free multi-provider
```

## Package Distribution

```toml
[project]
name = "ai-engine"
version = "4.0.0"
description = "Free multi-provider AI SDK — drop-in OpenAI & Anthropic compatibility"

[tool.hatch.build.targets.wheel]
packages = ["ai_engine", "core"]

[project.optional-dependencies]
server = ["fastapi>=0.104.0", "uvicorn", "jinja2", "aiofiles", "python-multipart"]
```

```bash
pip install ai-engine              # SDK only (minimal deps)
pip install ai-engine[server]      # SDK + web server + dashboard
```

## Key Difference from v1 Plan

| v1 Plan | v2 Plan |
|---------|---------|
| `from ai_engine import AIEngine` | `from ai_engine import OpenAI` |
| Custom class name | Same class name as official SDK |
| Developers learn new API | Developers use existing knowledge |
| One provider format | Multi-provider SDK support (OpenAI + Anthropic) |
| Custom response types | Standard SDK response types |
