# Post–Test-Harness Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the next safe, high-value improvements after the test-harness SDD (rotation mutmut ≥90%, scoped ruff, CI green) without publishing PyPI unless the user explicitly approves.

**Architecture:** Three parallel tracks—**hardening** (automate gates, docs), **dependency hygiene** (httpx 0.28 + Starlette TestClient), **maintainability** (lint `ai_engine/` then rest of repo)—plus an optional **release** track blocked on user consent. Each track is independently mergeable; default execution order is Track A → B → C.

**Tech Stack:** Python 3.10–3.12, pytest + pytest-timeout, ruff, mutmut 2.6, FastAPI/Starlette TestClient, httpx, GitHub Actions.

## Global Constraints

- Do **not** bump `pyproject.toml` `version` or publish to PyPI without **explicit user approval** (handoff constraint).
- Do **not** commit `data/config_overrides.json` or `mutants/`.
- CI must keep passing: `ruff check core tests` + `AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30`.
- Rotation mutmut gate must stay **≥90%** on the five-function chain after test changes (`_rotate_api_key`, `_select_optimal_key`, `_handle_provider_failure`, `_request_with_key_rotation`, `roll_api_key`).
- httpx pin today: `httpx>=0.27.0,<0.28.0` in `[project.optional-dependencies].dev`.

---

## Recommended order (human decision)

| Priority | Track | Effort | Risk | User gate |
|----------|-------|--------|------|-----------|
| **1** | A — Hardening & docs | ~1–2 h | Low | None |
| **2** | B — httpx 0.28 migration | ~2–4 h | Medium | None |
| **3** | C — Ruff `ai_engine/` (203 errs) | ~1–2 h | Low | None |
| **4** | C′ — Ruff full repo (~350) | ~3–6 h | Low | Optional scope |
| **5** | D — PyPI v1.0.3 | ~1 h | Medium | **Required** |
| **Stretch** | E — mutmut in CI (optional job) | ~2 h | Low | None |

---

## Track A: Hardening (do first)

### Task A1: Rotation mutmut gate script

**Files:**
- Create: `scripts/mutmut_rotation_gate.sh`
- Modify: `CONTRIBUTING.md` (add “Mutation testing” subsection)

**Interfaces:**
- Produces: exit `0` if kill rate ≥ threshold (default 90%), else `1` + stderr message.

- [ ] **Step 1: Add script**

```bash
#!/usr/bin/env bash
# scripts/mutmut_rotation_gate.sh — requires prior: mutmut run (full)
set -euo pipefail
THRESHOLD="${1:-90}"
python3 - <<'PY'
import json, sys
from pathlib import Path
p = Path("mutants/core/ai_engine.py.meta")
if not p.exists():
    print("missing mutants/core/ai_engine.py.meta — run: mutmut run", file=sys.stderr)
    sys.exit(2)
codes = json.loads(p.read_text())["exit_code_by_key"]
rot = ("_rotate_api_key", "_select_optimal_key", "_handle_provider_failure",
       "_request_with_key_rotation", "roll_api_key")
rc = {k: v for k, v in codes.items() if any(f in k for f in rot) and v in (0, 1)}
k = sum(1 for v in rc.values() if v == 1)
t = len(rc)
if t == 0:
    print("no rotation mutants evaluated", file=sys.stderr)
    sys.exit(2)
pct = 100 * k / t
thresh = float(__import__("os").environ.get("MUTMUT_ROTATION_THRESHOLD", sys.argv[1] if len(sys.argv) > 1 else "90"))
print(f"rotation chain: {k}/{t} = {pct:.1f}% (threshold {thresh}%)")
sys.exit(0 if pct >= thresh else 1)
PY
```

- [ ] **Step 2: chmod + smoke**

Run: `chmod +x scripts/mutmut_rotation_gate.sh && ./scripts/mutmut_rotation_gate.sh 90`  
Expected: `rotation chain: 391/421 = 92.9%` and exit 0 (if `mutants/` present from last run).

- [ ] **Step 3: Document in CONTRIBUTING.md**

Add after “Run Tests”:

```markdown
### Mutation testing (optional, local)

```bash
rm -rf mutants && mutmut run --max-children 4
./scripts/mutmut_rotation_gate.sh 90
```
```

- [ ] **Step 4: Commit**

```bash
git add scripts/mutmut_rotation_gate.sh CONTRIBUTING.md
git commit -m "chore: add mutmut rotation gate script and docs"
```

---

### Task A2: Refresh `.agent/continuation.md` on disk (optional commit)

**Files:**
- Modify: `.agent/continuation.md` (already updated locally in prior session)

- [ ] **Step 1:** If diff exists vs `origin/main`, commit as `docs: update continuation handoff after mutmut gate`.

*Note:* `.superpowers/sdd/progress.md` is gitignored—update locally only.

---

## Track B: httpx 0.28 + TestClient migration

**Why:** Dev pin `<0.28` due to Starlette/FastAPI TestClient + httpx API change; warnings already show deprecated `app=` shortcut.

**Files (expected touch):**
- Modify: `pyproject.toml` (`httpx`, possibly `starlette`, `fastapi` caps)
- Modify: `tests/conftest.py`, `tests/test_chat_router.py`, `tests/test_upload.py` (TestClient construction)
- Search: `grep -rn TestClient tests/`

**Interfaces:**
- Consumes: `from starlette.testclient import TestClient` or `httpx.ASGITransport(app=app)` per installed Starlette version docs.

### Task B1: Spike — bump httpx in branch, capture failures

- [ ] **Step 1: Worktree or branch**

```bash
git checkout -b chore/httpx-028
```

- [ ] **Step 2: Relax pin**

In `pyproject.toml` dev deps, change to `httpx>=0.28.0,<0.29.0` (exact upper bound TBD after spike).

- [ ] **Step 3: Reinstall + run tests**

```bash
pip install -e ".[dev,server]" --upgrade
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -q
```

Expected: failures or DeprecationWarnings pointing at TestClient / transport.

- [ ] **Step 4: Record failure output** in plan PR description (no commit until green).

### Task B2: Fix TestClient usage (TDD-friendly)

- [ ] **Step 1: Centralize client fixture**

Modify `tests/conftest.py` so **one** helper builds TestClient:

```python
import httpx
from starlette.testclient import TestClient

def make_test_client(app):
    transport = httpx.ASGITransport(app=app)
    return TestClient(transport=transport, base_url="http://testserver")
```

(Adjust if Starlette version requires different import—match spike.)

- [ ] **Step 2: Point `test_chat_router.py` / `test_upload.py` local fixtures at helper** or delete duplicate fixtures and use conftest `client` only.

- [ ] **Step 3: Run**

```bash
AI_ENGINE_MODE=testing pytest tests/test_chat_router.py tests/test_upload.py tests/conftest.py -q --timeout=30
```

Expected: PASS.

- [ ] **Step 4: Full non-live suite**

Expected: `712+ passed`, same skip count.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/
git commit -m "chore: migrate TestClient to httpx 0.28 ASGITransport"
```

### Task B3: Align server optional-deps caps

- [ ] **Step 1:** If spike requires newer Starlette/FastAPI, bump `[project.optional-dependencies].server` and `.dev` consistently; re-run CI matrix locally on 3.10 if possible.

- [ ] **Step 2:** Update CONTRIBUTING.md if install instructions change.

---

## Track C: Ruff expansion

**Current:** `ruff check core tests` → 0; `ruff check ai_engine` → **203**; full repo → **350** (155 auto-fixable).

### Task C1: Lint `ai_engine/` to CI parity

**Files:**
- Modify: `ai_engine/**/*.py` (mostly F401, W293, F841)
- Modify: `.github/workflows/test.yml`
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Auto-fix safe**

```bash
ruff check ai_engine --fix
ruff check ai_engine --fix --unsafe-fixes  # only after reviewing diff
```

- [ ] **Step 2: Manual F821/E402** in `ai_engine/server/app.py` if any remain (grep `ruff check ai_engine`).

- [ ] **Step 3: Extend CI**

```yaml
run: ruff check core tests ai_engine
```

- [ ] **Step 4: Full non-live pytest**

- [ ] **Step 5: Commit** `chore: extend ruff to ai_engine package`

### Task C2 (optional): Remaining ~147 errors outside ai_engine

Scope: `config.py`, scripts, TUI, etc. Same pattern—one directory per commit; expand CI only when directory is clean.

**Decision gate:** Ask user whether to enforce full-repo ruff in CI or keep phased directories.

---

## Track D: PyPI v1.0.3 (blocked)

**Do not start until user says “approve PyPI publish”.**

### Task D1: Release checklist (when approved)

**Files:**
- Modify: `pyproject.toml` `version = "1.0.3"`
- Modify: `CHANGELOG.md` or release notes (if present)
- Verify: `pip install build && python -m build`
- Verify: rotation gate script + non-live tests + `gh run list`

- [ ] **Step 1:** Summarize changelog from `3395565`, `dabb298`, `e1a7103` (test harness, rotation, ruff).
- [ ] **Step 2:** User runs publish (or delegates with explicit token)—agent must not `twine upload` without approval.

---

## Track E (stretch): mutmut in CI

**Not required for quality gate today** (full mutmut ~4+ min, 3339 mutants). Optional `workflow_dispatch` job:

- Install dev deps → `mutmut run` with timeout → `./scripts/mutmut_rotation_gate.sh 90`
- Cache `mutants/` optional; usually run on `main` weekly or pre-release.

### Task E1: `.github/workflows/mutmut.yml`

- [ ] `on: workflow_dispatch` only; `timeout-minutes: 30`; matrix 3.12 only.

---

## Verification commands (every track)

```bash
source .venv/bin/activate
ruff check core tests ai_engine   # after C1
AI_ENGINE_MODE=testing pytest tests/ -m "not live" --timeout=30 -q
./scripts/mutmut_rotation_gate.sh 90   # after any rotation test change
```

---

## Self-review (spec coverage)

| Deferred item (handoff) | Task |
|-------------------------|------|
| mutmut gate automation | A1 |
| httpx 0.28 | B1–B3 |
| Full-repo ruff | C1–C2 |
| PyPI v1.0.3 | D1 (gated) |
| CONTRIBUTING mutmut | A1 |

No placeholders; execution can start at **Task A1** without user approval except Track D.

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-07-14-post-harness-roadmap.md`

**Suggested next move for this repo:** Run **Track A** (gate script + CONTRIBUTING) in one short session, then **Track B** on a branch.

**Two execution options:**

1. **Subagent-driven (recommended)** — one subagent per task (A1, B1, …), review between tasks.
2. **Inline** — execute Track A now in this session, checkpoint before httpx spike.

**Which track should we start with—A (hardening), B (httpx), or C (ai_engine ruff)?**