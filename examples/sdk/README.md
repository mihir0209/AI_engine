# AI Synapse SDK Examples

Quick examples showing how to use the AI Synapse SDK.

## Prerequisites

```bash
pip install ai-synapse
```

No server required — the SDK routes through free providers directly.

## Quick Start

### Minimal Example

```python
from ai_engine import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### With API Keys

```python
from ai_engine import OpenAI

client = OpenAI(api_keys={
    "groq": "gsk_...",
    "gemini": "AI...",
    "openrouter": "sk-or-...",
})

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### With Config File

```python
from ai_engine import OpenAI

client = OpenAI(config="ai_engine/config.json")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## Streaming

```python
from ai_engine import OpenAI

client = OpenAI()

stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## Force a Provider

```python
from ai_engine import OpenAI

client = OpenAI()

# Force Groq (fast, free)
response = client.chat.completions.create(
    model="groq/llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Force Pollinations
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
    preferred_provider="pollinations"
)
```

## List Models

```python
from ai_engine import OpenAI

client = OpenAI()
models = client.models.list()
print(f"Available models: {len(models.data)}")
for m in models.data[:5]:
    print(f"  {m.id} (owned by {m.owned_by})")
```

## Check Vision Compatibility

```python
from ai_engine import OpenAI

client = OpenAI()

# Can this model handle images?
result = client.check_image_compatibility("gemini", "gemini-2.5-flash")
print(f"Compatible: {result['compatible']}")

result = client.check_image_compatibility("groq", "llama-3.3-70b-versatile")
print(f"Compatible: {result['compatible']}")
print(f"Try instead: {result['suggestions']}")
```

## Configuration via Environment Variables

```bash
export AI_ENGINE_API_KEY_GROQ=gsk_...
export AI_ENGINE_API_KEY_GEMINI=AI...
export AI_ENGINE_CDN_CONFIG=default
export AI_ENGINE_TIMEOUT=30
```

```python
from ai_engine import OpenAI
client = OpenAI()  # picks up env vars automatically
```

## Late Configuration

```python
import ai_engine

# Configure globally before creating clients
ai_engine.use(
    api_keys={"groq": "gsk_..."},
    cdn_config="default",
    timeout=60
)

client = ai_engine.OpenAI()
```

## Start Web Server

```python
from ai_engine import OpenAI

client = OpenAI()
client.serve(port=8000)
# Dashboard: http://localhost:8000
# Chat UI: http://localhost:8000/chat
# API Docs: http://localhost:8000/docs
```
