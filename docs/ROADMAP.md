# Maintainer roadmap

**Package:** [ai-synapse](https://pypi.org/project/ai-synapse/) **1.0.3** (2026-07-14)

## Shipped in 1.0.3

- Mock provider test harness (`AI_ENGINE_MODE=testing`), 712+ non-live tests
- API key rotation on preferred/default chat paths; mutmut rotation gate ≥90%
- httpx 0.28 + Starlette ≥0.37.2; ruff on `core`, `tests`, `ai_engine`
- Docs refresh (README, server, deployment, user guide)

## Open work (optional)

| Area | Notes |
|------|--------|
| Ruff | CI: `core`, `tests`, `ai_engine`, `scripts`, `chat_module`; optional: root `server.py`, `__init__.py` |
| CI | `mutmut.yml` workflow_dispatch for pre-release checks |
| Docs | Legacy files stubbed; primary path: README + ARCHITECTURE |
| Providers | Reliability, fallback chains, dashboard metrics — one feature per PR |
| Release | Next PyPI version only with explicit maintainer approval |

## How to develop

See [CONTRIBUTING.md](../CONTRIBUTING.md):

```bash
pip install -e ".[dev,server]"
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -q
ruff check core tests ai_engine scripts chat_module
```

## Detailed plan

Internal execution checklist: [post-release roadmap](superpowers/plans/2026-07-14-post-release-roadmap.md).