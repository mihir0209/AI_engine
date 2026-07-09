# Changelog

All notable changes to AI Synapse are documented here.

## [1.0.2] - 2026-07-09

### Fixed

- Integration tests no longer write to real `~/.ai-engine/chatdata/` (prevents accidental chat deletion)
- Env layering: `~/.ai-engine/.env` → `./.env` → `AI_SYNAPSE_ENV` → shell exports (documented in README)
- Per-user config: `~/.ai-engine/.env`, `~/.ai-engine/config.json`, `~/.ai-engine/data/` for pip installs

### Fixed (TUI)

- File picker routes non-image files through text inject (not vision attach)
- Generation binds to the chat that started it; block chat switch while streaming
- Persist partial assistant text when generation is stopped
- Surface session save failures instead of swallowing errors
- Remove `os.chdir` from worker threads; use absolute model cache path
- Cap attached image size at 20 MB; drop empty-stream auto-retry
- Harden `ChatStorage.load()` against corrupt `meta.json` IDs
- `python -m ai_engine tui` delegates to `run_tui()` for consistent init
- Slash fuzzy suggestions include provider, image, rename, delete, favorite

### Architecture (P2 review)

- TUI package moved to `ai_engine/tui/` (`app`, `widgets`, `screens`, `common`, `storage`, etc.)
- Split TUI into focused modules under `ai_engine/tui/`
- Shared routing deduped between `tui.py` and `tui_media.py`
- SSRF guard + download size cap for model image URLs in `tui_media`
- JSON export redacts home-directory prefixes from attachment paths
- Model cache discovery logs via `verbose_print` only (no stdout spam in TUI)
- PyPI classifier set to Beta until integration coverage matures

### Tests

- `tests/test_tui_media.py` — routing, URL allowlist, data-URI persistence
- `tests/test_tui_integration.py` — Textual Pilot mount, new chat, processing guard

## [1.0.1] - 2026-07-09

### Documentation

- README revamp: main chat + vision reply screenshots; link to full TUI guide
- New [docs/TUI.md](docs/TUI.md) with three terminal screenshots, shortcuts, and attachments
- Docs updated to use `pip install ai-synapse[server]` (removed obsolete `requirements_server.txt`)

### Repository cleanup

- Stop tracking build artifacts (`*.egg-info/`, `dist/`, `__pycache__/`)
- Remove committed runtime data (`data/workflows/workflows.json`); directory is gitignored and recreated locally
- `.agent/` kept local only; added to `.gitignore`

## [1.0.0] - 2026-07-08

### PyPI reset (important)

- **Version line reset:** `1.0.0` is the first canonical public release after the 4.x era.
- **Legacy 4.x yanked:** All `4.0.0`–`4.8.10` PyPI uploads were incremental test publishes and are **yanked** (hidden from default `pip install`, not deleted — PyPI policy).
- **Install:** `pip install "ai-synapse>=1.0.0"`

### Included in 1.0.0

- Multi-provider SDK (`from ai_engine import OpenAI`) with 27+ free providers
- Terminal TUI (`python -m ai_engine tui`) — model picker, `@` file attach, `/defaults`, collapsible sidebar
- Optional server extra (`pip install ai-synapse[server]`)
- Model cache, intent routing, per-chat personas, preferences

## [4.8.10] - 2026-07-14 (yanked on PyPI)

### Fixed (TUI Layout)
- Reintroduced robust chat-body container with height 1fr + dock: bottom on input-area to ensure input is always at the very bottom and message scroll area fills the space above it.
- This matches the desired ChatGPT-like layout from your reference image.
- Big centered welcome prompt now properly occupies the tall message area when empty.
- Messages will render in the area above the input.
- Tested structure: header (none), chat-body (1fr with scroll), input at bottom.

## [4.8.9] - 2026-07-14

### Fixed (TUI Layout Overhaul)
- Input area now properly pinned at the **bottom** of the chat pane (removed conflicting `dock` + extra wrapper; pure `1fr` VerticalScroll + auto input in vertical flow).
- Large message area (`#chat-scroll` with `height: 1fr`) now sits **above** the input, matching ChatGPT-style UIs.
- Empty state is a big, centered "Where should we begin?" prompt (styled with `height: 100%; content-align: center middle`).
- Messages (user + AI) now render visibly in the tall scroll area above the input bar.
- Removed unnecessary "Chat" header for cleaner, more spacious look.
- Input bar styling improved (darker rounded bar, better padding).
- Sidebar + New Chat button + history list preserved and functional.
- All previous fixes (Ctrl+Enter, commands, file picker via DirectoryTree modal, Command Palette on Ctrl+P, etc.) retained.

## [4.8.7] - 2026-07-07

### Fixed (TUI Publication Release)
- Full TUI overhaul published for isolated venv testing:
  - All chat sending, commands, image attaching, new chat, and history viewing now work reliably.
  - Proper Textual patterns for input (Ctrl+Enter handling), async workers, Markdown rendering, sidebar ListView switching.
  - Generalized clean chat UI (inspired by Elia and official Textual examples).
- Provider parameter forwarding fixed in SDK resources.
- Rebuilt and published via twine for clean `pip install` testing.

## [4.8.6] - 2026-07-07

### Fixed
- **TUI (Textual)**: Complete overhaul for functionality and UX
  - Ctrl+Enter sending now reliable (key handler + action)
  - Commands (/help, /clear, /image PATH [prompt], /model, /provider, /quit) functional
  - Image attaching + vision message formatting works
  - New chat, chat history sidebar with selection/switching
  - Proper async/threaded AI calls with UI updates via mount/call_from_thread
  - Provider= param correctly forwarded (resources + engine)
  - Uses Markdown for rich AI responses, improved CSS for generalized chat look
  - No more broken input handling or missing updates
- Provider routing param alias support in SDK resources
- Minor reactive/DOM safety in status watchers

### Changed
- TUI now generalized clean ChatGPT-style terminal interface (references: Elia patterns, official Textual LLM examples)
- Version bump to 4.8.6

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
