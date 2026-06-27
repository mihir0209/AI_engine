# Changelog

All notable changes to AI Engine are documented here.

## [3.1.0] - 2026-06-27

### Verified
- **OpenAI SDK v2.44.0 compatibility** — Full test pass with `openai` Python package
  - `client.models.list()` — 2349 models
  - `client.models.retrieve()` — single model lookup
  - `client.chat.completions.create()` — non-streaming
  - `client.chat.completions.create(stream=True)` — SSE streaming
  - Error format: `{error: {message, type, param, code}}`
  - `x-request-id` header on all responses

### Added
- **CDN Config Sync** — Auto-fetch latest provider configs from jsDelivr CDN (`CDN_CONFIG_URL=default`)
- **Vision Capability Detection** — Model-level vision/tool-calling database with pre-flight image checks
- **File Content Injection** — Uploaded text files are read and injected into AI prompts
- **Base64 Image Encoding** — Images encoded inline for vision-capable models
- **Health Ping Endpoint** — `POST /api/health/{name}/ping` sends live test requests
- **Auto-disable** — Providers auto-disable after 5 consecutive failures (5-min recovery)
- **Rate Limit Headers** — `X-RateLimit-*` headers on all API responses
- **Capabilities API** — `GET /api/capabilities` for provider/model capability queries
- **Chat Search** — Sidebar search across all chat messages
- **Chat Export** — Download conversations as Markdown
- **Message Regenerate** — Regenerate AI responses from any user message
- **Message Edit** — Edit user messages inline
- **File Upload UI** — Attach button, drag-and-drop, paste images in chat
- **POST /v1/models** — SDK compatibility for clients that POST to list models
- **SVG Favicon** — Added to all 5 HTML templates
- **pyproject.toml** — Ready for `pip install ai-engine`
- **CONTRIBUTING.md** — Contributor guidelines
- **tests/conftest.py** — Shared test fixtures (CDN disabled, cleanup)

### Changed
- **README rewritten** — Providers listed first, badges added, 4 provider categories
- **Quickstart updated** — Recommends Free Tier APIs over self-hosted Docker
- **Docker Compose** — Uses `.env` passthrough, g4f optional
- **Dockerfile** — Fixed broken `requirements_server.txt` reference
- **CI/CD** — Config validation step, install from requirements.txt
- **GitHub** — 20 topics added, description updated

### Fixed
- **Chat module broken imports** — `ai_engine` → `core.ai_engine`
- **Chat system prompt ignored** — Now prepended to AI context
- **Upload endpoint missing constants** — Restored `MAX_FILE_SIZE`, `ALLOWED_EXTENSIONS`
- **autodecide_cache AttributeError** — Fixed to use `shared_model_cache`
- **Duplicate /api/capabilities route** — Removed duplicate and dead sub-routes
- **g4f_nvidia wrong env var** — Was checking `MISTRAL_API_KEY`
- **statistics_manager import path** — Fixed `from core.statistics_manager import`
- **CLI save path** — Fixed to write to project root
- **CDN exec security** — Restricted to `os.getenv` only
- **Test-model endpoint** — Returns proper HTTP 502/500 status codes
- **WebSocket error cleanup** — Clears messageBuffer and removes orphaned DOM on error
- **Double-send prevention** — Send blocked while AI is responding
- **Rate limit atomicity** — Check+reset now under single lock
- **Enterprise auth O(1)** — API key lookup via index (was O(n) scan)

### Removed
- **Z AI / BigModel** — Requires credits, not free
- **providers/ package** — Abstract interface never used by engine
- **core/enhanced_health.py** — Dead code (only 1 test usage)
- **scripts/load_test.py** — Duplicate of core/load_test.py
- **Empty plugins/ directory**

### Architecture
- **Provider Request Mixin** — Extracted 735 lines from ai_engine.py into `core/provider_requests.py`
  - `AI_engine` inherits `ProviderRequestMixin`
  - `RequestResult` dataclass in provider_requests.py

## [3.0.0] - 2026-06-18

### Added
- Initial release with 27 providers
- OpenAI-compatible API
- Chat module with WebSocket streaming
- File uploads
- Plugin system
- Workflow engine
- Enterprise multi-tenancy
- 590 tests
