# Contributing to AI Engine

Thank you for considering contributing to AI Engine! This document provides guidelines for contributing.

## Getting Started

### Prerequisites
- Python 3.10+
- pip
- git

### Setup
```bash
# Clone the repository
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Install package with dev and server extras (required for tests)
pip install -e ".[dev,server]"
```

## Development Workflow

### 1. Create Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes
- Write code following style guidelines
- Add tests for new functionality
- Update documentation if needed

### 3. Run Tests

Default test runs use the mock provider harness and never hit live APIs:

```bash
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -q
```

The mock OpenAI-compatible server starts automatically on `127.0.0.1:18765` via pytest fixtures.

### 4. Commit
```bash
git add .
git commit -m "feat: description of changes"
```

## Commit Message Format

Use conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Adding tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance

Examples:
```
feat: add new provider support
fix: resolve rate limiting issue
docs: update API documentation
test: add integration tests
```

## Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to public functions
- Keep functions focused and small
- Run `ruff check core tests ai_engine scripts chat_module examples server.py config.py` before submitting (CI-enforced scope)

## Testing

### Non-live suite (default)

```bash
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -v
```

### Coverage

```bash
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --cov=core --cov=ai_engine \
  --cov-report=term-missing --cov-fail-under=40
```

### Specific test file

```bash
AI_ENGINE_MODE=testing pytest tests/features/test_key_rotation.py -v
```

### Live provider tests (optional)

Live tests are skipped by default. They require real API keys and may incur provider costs:

```bash
AI_ENGINE_RUN_LIVE_TESTS=1 AI_ENGINE_MODE=live pytest tests/ -m live -v
```

You can also trigger live tests manually via the **Live Tests** GitHub Actions workflow (`workflow_dispatch`).

### Mutation testing (key rotation)

Targets `core/ai_engine.py` rotation paths. Full run takes several minutes.

```bash
pip install -e ".[dev,server]"
# If source changed: rm -rf mutants
mutmut run --max-children 4
./scripts/mutmut_rotation_gate.sh 90   # exit 0 if rotation chain kill rate ≥ 90%
mutmut results                        # lists survivors only
```

## Environment Variables

| Variable | Values | Purpose |
|----------|--------|---------|
| `AI_ENGINE_MODE` | `testing`, `live`, `all` | Filter which providers load at runtime |
| `AI_ENGINE_RUN_LIVE_TESTS` | `1` | Opt in to `@pytest.mark.live` tests |

### `AI_ENGINE_MODE` semantics

| Mode | Providers loaded |
|------|------------------|
| `testing` | `modes: ["testing"]` only (mock `test_harness` for CI) |
| `live` | `modes: ["live"]` |
| `all` | Live-capable providers; **excludes** testing-only mocks |

Coverage: `tests/test_engine_modes.py`. Default in `tests/conftest.py` is `testing`.

## Releasing (maintainers)

PyPI publish requires **explicit approval** each time.

### Pre-release checklist

Before tagging a release, verify all items:

```bash
# 1. Tests pass across supported Python versions
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -q

# 2. Ruff is clean on all enforced scopes
ruff check core tests ai_engine scripts chat_module examples server.py config.py

# 3. Coverage gate passes
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -q \
  --cov=core --cov=ai_engine --cov-report=term-missing --cov-fail-under=40

# 4. Source-of-truth shims are intact
AI_ENGINE_MODE=testing pytest tests/test_source_of_truth.py -q --timeout=30

# 5. Config validation (no duplicate IDs, required fields)
python -c "
from config import AI_CONFIGS
ids = [c['id'] for c in AI_CONFIGS.values()]
assert len(ids) == len(set(ids)), 'Duplicate IDs'
for name, c in AI_CONFIGS.items():
    assert 'endpoint' in c, f'{name}: missing endpoint'
    assert 'model' in c, f'{name}: missing model'
    assert 'priority' in c, f'{name}: missing priority'
    assert 'modes' in c, f'{name}: missing modes'
assert 'test_harness' in AI_CONFIGS
print(f'Config OK: {len(AI_CONFIGS)} providers')
"

# 6. Optional: mutation testing (rotation kill rate >= 90%)
mutmut run --max-children 4
./scripts/mutmut_rotation_gate.sh 90
```

### Release steps

1. Update `CHANGELOG.md` and `pyproject.toml` `version`
2. Run all items in the pre-release checklist above
3. Commit: `git commit -m "chore: release vX.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Build: `python -m build && twine check dist/*`
6. Push: `git push origin main --tags`
7. `twine upload dist/*` **only after explicit maintainer approval**

## Pull Requests

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

CI runs the non-live suite on Python 3.10, 3.11, and 3.12 for every push and PR.

## Questions?

Open an issue on GitHub or join our community.