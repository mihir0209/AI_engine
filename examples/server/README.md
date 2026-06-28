# AI Synapse Server Examples

Examples for running AI Synapse as a web server with API and chat interface.

## Prerequisites

```bash
pip install ai-synapse[server]
# or
pip install -r requirements.txt
```

## Quick Start

### Start the server

```bash
python server.py
```

Server starts at `http://localhost:8000` with:
- Dashboard: `http://localhost:8000/`
- Chat UI: `http://localhost:8000/chat`
- API Docs: `http://localhost:8000/docs`
- Models: `http://localhost:8000/models`

## API Examples

### Chat Completion (OpenAI SDK compatible)

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### cURL

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Docker

```bash
docker compose up -d
```

## Environment Variables

```bash
# Provider API keys
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AI...

# Server config
ADMIN_API_KEY=your-admin-key
CORS_ORIGINS=*
CDN_CONFIG_URL=default
```
