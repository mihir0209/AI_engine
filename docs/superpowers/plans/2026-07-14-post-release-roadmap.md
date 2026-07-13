# Post–v1.0.3 Roadmap

> **For agentic workers:** Use superpowers:executing-plans or subagent-driven-development per task. Checkboxes track progress.

**Goal:** Improve maintainability and release hygiene after **1.0.3** (test harness, docs, PyPI) without another PyPI publish unless the user explicitly approves again.

**Current baseline (2026-07-14):**

| Check | Status |
|-------|--------|
| `main` @ `30272fc` | Pushed |
| PyPI | [ai-synapse 1.0.3](https://pypi.org/project/ai-synapse/1.0.3/) |
| CI ruff | `core` + `tests` + `ai_engine` → **0** |
| Non-live pytest | **712 passed**, ~18s |
| mutmut rotation gate | **92.9%** (local script exists) |
| Ruff outside CI | **~147** errors (mostly `scripts/`) |

## Global constraints

- **No** `version` bump / `twine upload` without **new** explicit user approval.
- Do not commit `data/config_overrides.json`, `mutants/`, `dist/`.
- Keep rotation mutmut ≥90% if rotation tests change.
- Verify: `ruff check core tests ai_engine` + `AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -q`.

---

## Recommended order

| # | Track | Value | Effort | Gate |
|---|--------|-------|--------|------|
| **1** | Housekeeping & release metadata | High | ~30 min | None |
| **2** | Ruff `scripts/` (+ optional root files) | Medium | ~1–2 h | None |
| **3** | Legacy docs consolidation | Medium | ~2–3 h | None |
| **4** | CI: mutmut + release checklist | Medium | ~1–2 h | None |
| **5** | Provider reliability / product | High long-term | Days | Product priorities |
| **6** | v1.0.4+ release | — | ~1 h | **User approval** |

---

## Track 1 — Housekeeping (start here)

### Task 1.1: Git tag + GitHub release (optional but recommended)

**Files:** none (git/gh only)

- [ ] Tag: `git tag -a v1.0.3 -m "ai-synapse 1.0.3 — test harness, key rotation, docs"` on `30272fc`
- [ ] Push: `git push origin v1.0.3`
- [ ] Create GitHub Release with body copied from `CHANGELOG.md` [1.0.3] section

```bash
gh release create v1.0.3 --title "v1.0.3" --notes-file /tmp/notes.md
```

### Task 1.2: Refresh handoff + close old plan

**Files:**
- Modify: `.agent/continuation.md` (recent commits: `30272fc`, `66fbdf2`, `2b0044a`, `18eb23c`)
- Modify: `docs/superpowers/plans/2026-07-14-post-harness-roadmap.md` — add banner “Tracks A–D complete as of 1.0.3; see post-release roadmap”

- [ ] Update CI lint line to `ruff check core tests ai_engine`
- [ ] Mark mutmut script + httpx + ruff ai_engine + PyPI as done
- [ ] Point “next” to this file

### Task 1.3: PyPI smoke (read-only)

```bash
pip install 'ai-synapse==1.0.3' -q && python -c "from ai_engine import __version__; print(__version__)"
```

Expected: `1.0.3`

---

## Track 2 — Ruff phase 2 (`scripts/`)

**Why:** ~147 repo errors remain; `scripts/` is the main bucket; `core`/`tests`/`ai_engine` already clean.

### Task 2.1: Clean `scripts/`

```bash
ruff check scripts --fix
ruff check scripts --fix --unsafe-fixes   # review diff
ruff check scripts                        # target 0
```

**Files:** `scripts/*.py` (cli, audit, diagnose, etc.)

- [ ] Manual fix any remaining F821 (undefined names)
- [ ] Commit: `chore: ruff clean scripts/`

### Task 2.2: Decide CI expansion

**Option A (minimal):** Leave CI as `core tests ai_engine`; scripts cleaned for dev UX only.

**Option B (stricter):** Add `scripts` to `.github/workflows/test.yml`:

```yaml
run: ruff check core tests ai_engine scripts
```

- [ ] User/agent picks A or B before editing `test.yml`

### Task 2.3: Root / misc (optional)

```bash
ruff check . --exclude mutants --statistics
```

Phased dirs if needed: repo root `config.py` (already clean), any remaining single files.

---

## Track 3 — Legacy documentation

**Problem:** Large stale docs confuse contributors; primary path is README + focused `docs/*.md`.

| File | Action |
|------|--------|
| `docs/AI_ENGINE_DOCUMENTATION.md` | Archive or replace with pointer to README + ARCHITECTURE |
| `docs/SUBMISSION.md` | Archive if obsolete (PyPI submission one-off) |
| `docs/claude.md` | Merge useful bits into CONTRIBUTING or delete |
| `.agent/plans/*` (2026-06*) | Keep in `.agent/` only; add `docs/ROADMAP.md` one-pager for humans |

### Task 3.1: Add `docs/ROADMAP.md` (maintainer-facing)

Single page:

- What shipped in 1.0.3
- Open optional work (this plan’s tracks 2–5)
- Link to CONTRIBUTING + post-release plan

### Task 3.2: Trim or stub legacy files

At top of each legacy doc:

```markdown
> **Note:** Superseded by [README](../README.md) and [ARCHITECTURE.md](ARCHITECTURE.md). Kept for history.
```

Or move to `docs/archive/` in one commit.

- [ ] Commit: `docs: consolidate roadmap and stub legacy guides`

---

## Track 4 — CI hardening (stretch)

### Task 4.1: `mutmut.yml` workflow_dispatch

**Create:** `.github/workflows/mutmut.yml`

```yaml
name: Mutation tests
on:
  workflow_dispatch:
jobs:
  mutmut:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev,server]"
      - run: mutmut run --max-children 4
      - run: ./scripts/mutmut_rotation_gate.sh 90
```

Not on every push (runtime cost).

### Task 4.2: Pre-release checklist in CONTRIBUTING

Add subsection **Releasing** (no automation):

1. `CHANGELOG.md` + version in `pyproject.toml`
2. Full non-live pytest
3. Optional: mutmut gate
4. `python -m build` + `twine check`
5. Publish only with maintainer approval

---

## Track 5 — Product / providers (when you want features)

From older `.agent/plans/2026-06-21-next-steps.md` — still valid directionally:

| Item | Suggestion |
|------|------------|
| Rate-limited providers | Exponential backoff already partial; audit `_handle_provider_failure` + queue |
| Fallback chains | Configurable per-provider chains in `config.json` |
| Usage dashboard | Server metrics already exist; wire dashboard UI |
| Model capabilities | Extend `core/capabilities.py` + `/api/modalities` |
| Live test cadence | Run `live-tests.yml` monthly; document key rotation in prod |

**Approach:** One small TDD feature per branch; no mega-refactor.

**First concrete slice (if picking product now):**

- Task 5.1: Add integration test for `scripts/cli.py` `list_providers` output shape (if CLI still used) OR
- Task 5.2: Document + test `AI_ENGINE_MODE=all` vs `live` in CONTRIBUTING with one new pytest

---

## Track 6 — Next PyPI release (blocked)

Only when user says approve publish:

1. Bump `1.0.4` (or semver as agreed)
2. CHANGELOG from commits since `30272fc`
3. Tracks 1–2 done (at minimum)
4. `build` + `twine upload`

---

## Quick pick — what to run **next session**

**Fast path (1–2 hours):**

1. Track 1 (tag + release + handoff)
2. Track 2.1 (`scripts/` ruff)

**Quality path (half day):**

1. Track 1 + 2 + 4.2
2. Track 3.1 (`docs/ROADMAP.md` only)

**Feature path:**

- Track 5.2 or a single provider-reliability fix with tests

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-07-14-post-release-roadmap.md`

Reply with:

- **fast** — Track 1 + 2.1 inline now  
- **quality** — 1 + 2 + CONTRIBUTING release section  
- **feature** — name area (providers / dashboard / docs only)  
- **tag** — only GitHub release + tag

Default recommendation: **fast** (tag + `scripts/` ruff).