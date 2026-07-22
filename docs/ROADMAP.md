# Maintainer roadmap

**Package:** [ai-synapse](https://pypi.org/project/ai-synapse/) **1.0.3** (2026-07-14)

## Shipped in 1.0.3

- Mock provider test harness (`AI_ENGINE_MODE=testing`), 712+ non-live tests
- API key rotation on preferred/default chat paths; mutmut rotation gate ≥90%
- httpx 0.28 + Starlette ≥0.37.2; ruff on `core`, `tests`, `ai_engine`
- Docs refresh (README, server, deployment, user guide)

## Completed post-release work

| Area | Status |
|------|--------|
| Ruff `scripts/` | Clean — CI scope covers `core tests ai_engine scripts chat_module examples server.py config.py` |
| Source of truth | **Done:** packaged server/chat/config; TUI `routing_engine`; `tests/test_source_of_truth.py` |
| Provider reliability v2 | **Done:** exponential backoff per provider, configurable fallback chains, `BackoffTracker` |
| Observability integration | **Done:** normalized provider snapshots feed the dashboard |
| Legacy docs consolidation | **Done:** archived `AI_ENGINE_DOCUMENTATION.md`, `SUBMISSION.md`, `claude.md` |
| CI pre-release checklist | **Done:** documented in `CONTRIBUTING.md` |
| Monthly live test cadence | **Done:** cron schedule `0 8 1 * *` in `live-tests.yml` |
| Anthropic SDK | **Done:** drop-in `Anthropic`/`AsyncAnthropic` with message format conversion |

## Next release (requires explicit maintainer approval)

| Area | Notes |
|------|--------|
| Release | `v1.0.4` — PyPI publish only with explicit approval |
| Provider hardening | Extended retry policies, per-provider circuit breaker tuning |
| Distribution | Redis/Memcached caching, Kubernetes manifests, Grafana dashboards |