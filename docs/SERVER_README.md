# AI Synapse — Server

Production-oriented **FastAPI** app: OpenAI-compatible REST API, web dashboard, provider management, chat module, and metrics. Ships as the `[server]` extra (`pip install ai-synapse[server]`).

## Quick start

```bash
pip install ai-synapse[server]
mkdir -p ~/.ai-engine && cp .env.example ~/.ai-engine/.env
# add API keys to ~/.ai-engine/.env

python -m ai_engine serve
# or: ai-engine serve --host 0.0.0.0 --port 8000
```

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/` | Dashboard |
| `http://localhost:8000/chat` | Web chat UI |
| `http://localhost:8000/docs` | Swagger |
| `http://localhost:8000/v1/chat/completions` | OpenAI-compatible chat |
| `http://localhost:8000/v1/models` | Model list (cached + discovery) |
| `http://localhost:8000/health` | Health check |

## What you get

- **OpenAI-compatible** `/v1/*` endpoints (chat, models, audio, images where configured)
- **Universal** `/v1/uni` — intent-based routing (chat, TTS, embeddings, image gen)
- **Provider management** — priorities, enable/disable, key rotation stats
- **Chat module** — persisted chats, WebSocket streaming, file uploads
- **Observability** — latency, rate limits, SLA hooks, Prometheus-friendly metrics

## SDK-only vs server

| Need | Install | Run |
|------|---------|-----|
| Library in your app | `pip install ai-synapse` | `from ai_engine import OpenAI` |
| Local API + dashboard | `pip install ai-synapse[server]` | `python -m ai_engine serve` |
| Terminal chat | `pip install ai-synapse[tui]` or `[all]` | `python -m ai_engine tui` |

The server uses the same `core` routing engine as the SDK (`AI_engine`, key rotation, failover). No separate “server-only” provider list.

## Configuration

Same env layering as the README: `~/.ai-engine/.env` → `./.env` → `AI_SYNAPSE_ENV` → shell.

Optional admin protection for management routes:

```bash
export ADMIN_API_KEY=your-secret
```

CDN provider sync (optional):

```bash
CDN_CONFIG_URL=default
CDN_CONFIG_TTL=86400
```

See [USER_GUIDE.md](USER_GUIDE.md) and [DEPLOYMENT.md](DEPLOYMENT.md).

## Production

```bash
pip install ai-synapse[server]
uvicorn ai_engine.server.app:app --host 0.0.0.0 --port 8000 --workers 4
```

Or Docker: [DEPLOYMENT.md](DEPLOYMENT.md).

## Development (from git clone)

```bash
pip install -e ".[dev,server]"
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -q
python -m ai_engine serve
```

Use `AI_ENGINE_MODE=testing` only for tests; production and local dev with real keys should use `live` or `all` as documented in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Related docs

- [API.md](API.md) — endpoint reference
- [ARCHITECTURE.md](ARCHITECTURE.md) — routing and failover
- [SECURITY.md](SECURITY.md) — keys and exposure