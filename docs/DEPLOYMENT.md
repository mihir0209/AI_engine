# Deployment Guide

## Quick start

### pip install (recommended)

```bash
pip install ai-synapse[server]
mkdir -p ~/.ai-engine
cp .env.example ~/.ai-engine/.env   # add provider API keys

python -m ai_engine serve
# Dashboard: http://localhost:8000
```

### Git clone (development or custom builds)

```bash
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[server]"

cp .env.example .env
python -m ai_engine serve
```

### Docker

```bash
docker compose up -d
```

Server listens on port **8000** by default. See `docker-compose.yml` and `Dockerfile` in the repo for volumes and env.

## Production ASGI

```bash
pip install ai-synapse[server]
uvicorn ai_engine.server.app:app --host 0.0.0.0 --port 8000 --workers 4
```

Put TLS and rate limiting behind nginx, Caddy, or a cloud load balancer. Set `ADMIN_API_KEY` if exposing management APIs.

## Environment variables

### Provider keys

Set in `~/.ai-engine/.env`, project `.env`, or container env. See [collect_api.md](collect_api.md) and [`.env.example`](../.env.example).

### Server / engine

| Variable | Purpose |
|----------|---------|
| `AI_ENGINE_MODE` | `live` / `all` for production; never `testing` in prod |
| `ADMIN_API_KEY` | Protect sensitive management routes |
| `CDN_CONFIG_URL` | `default` or custom URL for remote provider config sync |
| `CDN_CONFIG_TTL` | Refresh interval (seconds) |

### Testing / CI

| Variable | Purpose |
|----------|---------|
| `AI_ENGINE_MODE=testing` | Mock provider only (`127.0.0.1:18765`) |
| `AI_ENGINE_RUN_LIVE_TESTS=1` | Opt into live pytest markers |

## Data paths

| Path | Contents |
|------|----------|
| `~/.ai-engine/.env` | API keys |
| `~/.ai-engine/config.json` | User overrides |
| `~/.ai-engine/data/` | Model cache, CDN cache |
| Project `chat_data.db` / uploads | Server chat module (when run from clone) |

## Health checks

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/v1/models -H "Authorization: Bearer dummy"
```

## Upgrades

```bash
pip install -U "ai-synapse[server]"
ai-engine version
```

Release notes: [CHANGELOG.md](../CHANGELOG.md).