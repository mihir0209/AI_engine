# User Guide

## Quick Start

### Option 1: pip install (Recommended)

```bash
pip install ai-synapse[all]
python -m ai_engine tui          # terminal chat
python -m ai_engine serve        # or local API server
```

### Option 2: Clone & Run

```bash
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
cp .env.example .env   # Add your API keys
python -m ai_engine serve
```

See [TUI.md](TUI.md) for the terminal chat UI.

### Option 3: Docker

```bash
docker compose up -d
```

Server starts at `http://localhost:8000`. Dashboard at `/`, API docs at `/docs`.

---

## CDN Config Sync (Auto-Update Providers)

AI Engine can auto-fetch the latest provider configurations from GitHub via jsDelivr CDN.

```bash
# In .env
CDN_CONFIG_URL=default        # Auto-URL from GitHub
CDN_CONFIG_TTL=86400          # Re-fetch every 24h
CDN_CONFIG_BRANCH=main        # Git branch
```

Or set a custom URL:
```bash
CDN_CONFIG_URL=https://raw.githubusercontent.com/you/repo/main/config.py
```

Disable CDN (use local config only):
```bash
CDN_CONFIG_URL=               # Empty = disabled
```

Check CDN status:
```bash
curl http://localhost:8000/api/cdn-config
```

Force refresh:
```bash
curl -X POST http://localhost:8000/api/cdn-config/refresh
```

---

## Chat Interface

### File Upload

- **Attach button** (paperclip icon) in the message input area
- **Drag and drop** files onto the chat area
- **Paste images** from clipboard (Ctrl+V / Cmd+V)

**Supported formats:**
- Text: .txt, .md, .json, .csv, .py, .js, .ts, .html, .css, .yaml, .yml, .xml
- Images: .png, .jpg, .jpeg, .gif, .webp
- Max size: 10MB

**How it works:**
- Text files are read and injected into the AI prompt as code blocks
- Images are encoded as base64 and sent to vision-capable models
- Non-vision models receive a "[Image attached - not supported]" placeholder

### Vision Models

AI Engine detects which providers support vision and shows warnings when you upload images to non-vision providers.

**Vision-capable providers:**
- Gemini (all models)
- OpenRouter (gemini, gpt-4o-mini, llama-4)
- Mistral (pixtral-large)
- Kilo (nemotron-ultra-vl)
- ZAI (glm-4.7-flash, glm-4.5-flash, glm-4.6v-flash)

### Chat Search

Type in the search bar in the sidebar to search across all chat messages.

### Chat Export

Click the download icon in the chat header to export as Markdown.

### Message Regenerate

Click the regenerate icon (redo) on any user message to regenerate the AI response from that point.

---

## API Usage

### OpenAI SDK (Python)

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

# Non-streaming
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)

# Streaming
for chunk in client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### cURL

```bash
# Non-streaming
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello!"}]}'

# Streaming
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello!"}], "stream": true}'
```

### List Models

```bash
curl http://localhost:8000/v1/models
```

### Force Provider

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Preferred-Provider: groq" \
  -d '{"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Hello!"}]}'
```

---

## Provider Health

### Ping a Provider

```bash
curl -X POST http://localhost:8000/api/health/groq/ping
```

Response:
```json
{"provider": "groq", "alive": true, "status_code": 200, "latency_ms": 450}
```

### Check Vision Compatibility

```bash
curl "http://localhost:8000/api/capabilities/check-image/groq?model=llama-3.3-70b-versatile"
```

Response:
```json
{"compatible": false, "reason": "does not support image input", "suggestions": ["gemini", "openrouter"]}
```

### Auto-disable

Providers auto-disable after 5 consecutive failures and recover after 5 minutes (or on first successful request).

---

## Configuration

### Provider API Keys

Edit `.env`:

```bash
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AI...
OPENROUTER_API_KEY=sk-or-...
# See .env.example for all providers
```

### Hot Reload

Reload config without restarting:

```bash
curl -X POST http://localhost:8000/api/config/reload
```

### Toggle Provider

```bash
curl -X POST http://localhost:8000/api/providers/groq/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

---

## Billing (Enterprise)

### Get Usage

```bash
curl "http://localhost:8000/api/billing/usage?tenant_id=tenant_123"
```

### Get Invoices

```bash
curl "http://localhost:8000/api/billing/invoices?tenant_id=tenant_123"
```

### Cost Alerts

```bash
curl "http://localhost:8000/api/billing/alerts?tenant_id=tenant_123&threshold=100"
```

---

## Monitoring

```bash
curl http://localhost:8000/health              # Health check
curl http://localhost:8000/api/status           # Engine status
curl http://localhost:8000/api/health/providers # Provider health
curl http://localhost:8000/api/statistics       # Usage stats
curl http://localhost:8000/metrics              # Prometheus metrics
```

---

## Interactive API Docs

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Server won't start | Check port 8000, verify deps installed, check `.env` |
| "No available providers" | Add API keys in `.env`, check `/api/providers/health` |
| Provider errors | Check API key validity, check rate limits |
| File upload fails | Max 10MB, check extension is allowed |
| Images not processed | Switch to a vision provider (Gemini, OpenRouter) |
| CDN config not updating | Check `CDN_CONFIG_URL` in `.env`, call `/api/cdn-config/refresh` |
| Streaming hangs | Normal for non-streaming providers — response arrives in chunks |
