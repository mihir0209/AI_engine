# User Guide

## Quick start

### pip install (recommended)

```bash
pip install ai-synapse[all]    # SDK + server + TUI
python -m ai_engine tui          # terminal chat (optional)
python -m ai_engine serve        # local OpenAI-compatible API + dashboard
```

### Clone & run

```bash
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
cp .env.example .env             # add API keys
python -m ai_engine serve
```

### Docker

```bash
docker compose up -d
```

- Dashboard: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`
- OpenAI base URL: `http://localhost:8000/v1/`

See [TUI.md](TUI.md) for the terminal chat UI.

---

## Web dashboard

After `python -m ai_engine serve`:

- **Home** — provider status, quick stats
- **Chat** — `/chat` — multi-turn chats, attachments, model/provider selection
- **API** — use `/docs` for interactive OpenAI-compatible calls

Point external tools at `http://localhost:8000/v1` with any API key string if auth is not enforced for chat routes.

---

## CDN config sync (optional)

Auto-fetch provider definitions from GitHub via jsDelivr:

```bash
# In .env or ~/.ai-engine/.env
CDN_CONFIG_URL=default
CDN_CONFIG_TTL=86400
CDN_CONFIG_BRANCH=main
```

Custom URL:

```bash
CDN_CONFIG_URL=https://raw.githubusercontent.com/you/repo/main/config.py
```

Disable:

```bash
CDN_CONFIG_URL=
```

Check status:

```bash
curl http://localhost:8000/api/cdn-config
```

---

## Configuration layers

1. Shell environment (highest)
2. `AI_SYNAPSE_ENV=/path/to/profile.env`
3. `./.env` in project directory
4. `~/.ai-engine/.env` (global)

See [README](../README.md#configuration) for details.

---

## More documentation

| Doc | Topic |
|-----|--------|
| [SERVER_README.md](SERVER_README.md) | Server features |
| [API.md](API.md) | REST reference |
| [collect_api.md](collect_api.md) | Free API keys |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Docker & production |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Developers & tests |