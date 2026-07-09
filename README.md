# AI Synapse

[![PyPI](https://img.shields.io/pypi/v/ai-synapse)](https://pypi.org/project/ai-synapse/)
[![Python](https://img.shields.io/pypi/pyversions/ai-synapse)](https://pypi.org/project/ai-synapse/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Free multi-provider AI SDK** with drop-in OpenAI compatibility, intelligent routing across 27+ providers, and an optional local server. Use it as a Python library, run your own OpenAI-compatible API, or add the terminal chat UI on top.

```bash
pip install ai-synapse              # SDK — routing, failover, OpenAI client
pip install ai-synapse[server]      # SDK + local OpenAI-compatible server
pip install ai-synapse[all]         # SDK + server + terminal chat (TUI)
```

---

## Python SDK

Drop-in `OpenAI` client that routes requests across free-tier and self-hosted providers with automatic failover, key rotation, and model caching.

```python
from ai_engine import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

**CLI** (included with the SDK):

```bash
ai-engine chat "Explain quantum tunneling"
ai-engine providers
ai-engine version
```

More examples: [`examples/sdk/`](examples/sdk/)

---

## Local server

Run an OpenAI-compatible HTTP API on your machine — same routing engine as the SDK, plus a web dashboard, provider management, metrics, and chat persistence.

```bash
mkdir -p ~/.ai-engine && cp .env.example ~/.ai-engine/.env
# edit ~/.ai-engine/.env — add provider API keys

pip install ai-synapse[server]
python -m ai_engine serve
```

| Endpoint | URL |
|----------|-----|
| OpenAI API | `http://localhost:8000/v1/` |
| Swagger UI | `http://localhost:8000/docs` |
| Health | `http://localhost:8000/health` |

Point any OpenAI SDK or tool at `base_url="http://localhost:8000/v1"`:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Routed through AI Synapse server"}],
)
```

Server docs: [API reference](docs/API.md) · [Server guide](docs/SERVER_README.md) · [Deployment](docs/DEPLOYMENT.md)

---

## Configuration

Provider API keys and settings load in **layers**. When the same variable appears in multiple places, the **higher layer wins**. Different names are **merged**.

| Priority | Source | Typical use |
|----------|--------|-------------|
| **1** (highest) | Shell / container env (`export GROQ_API_KEY=…`) | CI, Docker, secrets managers |
| **2** | `AI_SYNAPSE_ENV=/path/to/profile.env` | Named profiles (`work.env`, `personal.env`) |
| **3** | `./.env` in the **current working directory** | Git clone, venv, per-project overrides |
| **4** (lowest) | `~/.ai-engine/.env` | Global config after `pip install` (any cwd) |

### Global setup (pip install)

```bash
mkdir -p ~/.ai-engine
cp .env.example ~/.ai-engine/.env
# edit ~/.ai-engine/.env — GROQ_API_KEY, OPENROUTER_API_KEY, etc.
```

### Project overrides (venv / git clone)

```bash
# ~/.ai-engine/.env     → shared keys
# ./.env                → overrides only what differs in this project
pip install -e ".[server]"
python -m ai_engine serve
```

### Explicit profile

```bash
AI_SYNAPSE_ENV=~/configs/ai-work.env python -m ai_engine serve
```

### Optional paths

| File | Purpose |
|------|---------|
| `~/.ai-engine/config.json` | Provider priorities / enable flags |
| `~/.ai-engine/data/` | Model cache, CDN config cache |

See [`.env.example`](.env.example) and [provider keys guide](docs/collect_api.md).

---

## Terminal chat (optional)

A Textual-based terminal UI for interactive chat — built on the same SDK routing layer. Install only if you want a local chat app in the terminal.

```bash
pip install ai-synapse[tui]    # or ai-synapse[all]
python -m ai_engine tui
```

![Main chat](docs/images/tui_1_main_chat.png)

Sidebar history, model/provider routing, slash commands, `@` file attach, and vision support. Full walkthrough: **[docs/TUI.md](docs/TUI.md)**.

---

## Documentation

| Doc | Contents |
|-----|----------|
| [API reference](docs/API.md) | HTTP endpoints (server) |
| [Server guide](docs/SERVER_README.md) | Dashboard, providers, metrics |
| [User guide](docs/USER_GUIDE.md) | Web dashboard & chat UI |
| [Architecture](docs/ARCHITECTURE.md) | Routing, failover, caching |
| [Provider keys](docs/collect_api.md) | Free-tier signup |
| [Deployment](docs/DEPLOYMENT.md) | Docker, production |
| [TUI guide](docs/TUI.md) | Terminal chat (optional) |

---

## Development

```bash
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,all]"
pytest tests/
```

---

## License

MIT — see [LICENSE](LICENSE).