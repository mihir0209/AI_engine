# AI Engine - Free AI Inference Router for Developers

[![Tests](https://img.shields.io/badge/tests-518%20passing-brightgreen)]()
[![Providers](https://img.shields.io/badge/providers-21%20working-blue)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI-Compatible-412991)]()
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)]()

> **Stop paying for AI inference.** Route your requests through 21+ free providers with automatic failover, intelligent routing, and OpenAI-compatible API.

---

## Free Providers

### No API Key Required (Truly Free)

| Provider | Model | Endpoint |
|----------|-------|----------|
| **Pollinations** | openai | `text.pollinations.ai/openai` |
| **Hermes** | Hermes-3-Llama | `hermes.ai.unturf.com/v1` |
| **G4F Groq** | llama-3.3-70b | `g4f.space/api/groq` |
| **G4F Gemini** | gemini-2.5-flash | `g4f.space/api/gemini` |
| **G4F NVIDIA** | nemotron-3 | `g4f.space/api/nvidia` |
| **OpenCode Zen** | north-mini-code | `opencode.ai/zen/v1` |

### Free Tier APIs (Signup Required)

| Provider | Free Tier | Signup |
|----------|-----------|--------|
| **Groq** | 30 RPM, 14,400 RPD | [console.groq.com](https://console.groq.com) |
| **OpenRouter** | 23 free models | [openrouter.ai](https://openrouter.ai) |
| **Gemini** | 5-30 RPM | [aistudio.google.com](https://aistudio.google.com) |
| **NVIDIA** | 40 RPM | [build.nvidia.com](https://build.nvidia.com) |
| **Cerebras** | 30 RPM | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| **Cloudflare** | 10K neurons/day | [dash.cloudflare.com](https://dash.cloudflare.com) |
| **GitHub** | Varies | [github.com/marketplace](https://github.com/marketplace/models) |
| **Vercel** | $5/month free | [vercel.com](https://vercel.com) |
| **Cohere** | 20 RPM, 1K/month | [cohere.com](https://cohere.com) |
| **Mistral** | 1 RPS, 500K tokens/min | [console.mistral.ai](https://console.mistral.ai) |
| **HuggingFace** | $0.10/month | [huggingface.co](https://huggingface.co) |
| **Kilo** | Auto free routing | [app.kilo.ai](https://app.kilo.ai) |

### Custom Providers (Your Keys)

| Provider | Models | Signup |
|----------|--------|--------|
| **hcnsec** | [Various](https://api.hcnsec.cn/pricing) | [api.hcnsec.cn](https://api.hcnsec.cn) |
| **LLM7** | [Various](https://docs.llm7.io/guides/models) | [llm7.io](https://llm7.io) |
| **PaxSenix** | [Various](https://api.paxsenix.org/v1/models) | [api.paxsenix.org](https://api.paxsenix.org) |

### Self-Hosted Options

| Provider | Setup | Models |
|----------|-------|--------|
| **GPT4Free** | `docker run -p 8080:8080 hlohaus789/g4f` | GPT-4o, Claude, Gemini |
| **Ollama** | `curl -fsSL https://ollama.com/install.sh \| sh` | Llama, Mistral, etc. |

---

## Quick Start

### Option 1: Free Tier APIs (Recommended)

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Get free API keys (see guide below)
# 3. Add keys to .env file
# 4. Start server
python server.py
```

### Option 2: Self-Hosted (No API Keys Needed)

```bash
# Start g4f server
docker run -d -p 8080:8080 hlohaus789/g4f

# Start AI Engine
python server.py
```

---

## For Developers

### OpenAI SDK Compatible

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # Not needed for free providers
)

# Chat completion
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)

# Streaming
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### cURL

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### JavaScript

```javascript
import OpenAI from 'openai';

const client = new OpenAI({
    baseURL: 'http://localhost:8000/v1',
    apiKey: 'dummy'
});

const response = await client.chat.completions.create({
    model: 'gpt-4',
    messages: [{ role: 'user', content: 'Hello!' }]
});
```

---

## Features

### Core
- OpenAI-compatible API with streaming
- Automatic provider failover
- Intelligent key rotation
- Response caching with TTL

### Intelligence
- Task-based model selection
- Cost optimization
- Latency tracking
- A/B testing

### Enterprise
- Multi-tenancy with quotas
- RBAC (Admin/User/Viewer)
- Audit logging
- Billing tracking

### Platform
- Plugin system
- Workflow engine
- CLI tool
- Docker deployment

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (OpenAI-compatible, supports `stream: true`) |
| `/v1/models` | GET/POST | List all models |
| `/api/providers` | GET | List providers |
| `/api/health/{name}/ping` | POST | Live health ping for a provider |
| `/api/capabilities` | GET | Provider/model capabilities (vision, etc.) |
| `/api/status` | GET | Engine status |
| `/api/statistics` | GET | Usage statistics |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |
| `/docs` | GET | Swagger UI (interactive API explorer) |
| `/redoc` | GET | ReDoc API documentation |

### Rate Limit Headers

All API responses include:
- `X-RateLimit-Limit` — Max requests per minute
- `X-RateLimit-Remaining` — Remaining requests in current window

---

## Documentation

- [API Reference](docs/API.md)
- [User Guide](docs/USER_GUIDE.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Security Guide](docs/SECURITY.md)
- [Provider Setup](docs/collect_api.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License - See [LICENSE](LICENSE)
