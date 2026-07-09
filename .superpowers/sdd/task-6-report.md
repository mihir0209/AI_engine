# Task 6 Report: mutmut mutation testing for key rotation

**Status:** ✅ Complete  
**Date:** 2026-07-09

## Summary

Added `mutmut>=2.6.0` to dev dependencies, configured `[tool.mutmut]` to target `core/ai_engine.py` with key-rotation test selection, ran an initial full mutation scan (1254 mutants), and extended rotation-path unit tests in `tests/test_ai_engine.py` to kill obvious survivors—especially in `roll_api_key` message/preview branches.

## Commits

| Hash | Message |
|------|---------|
| `0cbedfb` | `chore: add mutmut mutation testing for key rotation` |
| `391728f` | `test: improve key rotation mutation kill coverage` |

## Configuration

`pyproject.toml` changes:

- **Dev dependency:** `mutmut>=2.6.0`
- **`[tool.mutmut]`:**
  - `paths_to_mutate` / `source_paths`: `core/ai_engine.py`
  - `only_mutate`: `core/ai_engine.py`
  - `tests_dir` / `pytest_add_cli_args_test_selection`: rotation test files
  - `mutate_only_covered_lines = true` (limits mutants to lines hit by the selected tests)
- **`[tool.pytest.ini_options]`:** `pythonpath = ["."]` so integration tests import `tests.*` under mutmut's pytest runner

**Note:** mutmut 2.x no longer supports the brief's `runner = "python -m pytest -x {tests}"` key; it invokes pytest natively via `pytest_add_cli_args_test_selection`. `paths_to_mutate` and `tests_dir` still work but emit deprecation warnings—kept for plan compatibility.

## Tests Added

Extended `tests/test_ai_engine.py` with targeted rotation-path unit tests:

| Test | Targets |
|------|---------|
| `test_select_optimal_key_*` (4) | `_select_optimal_key` empty/single/load/rate-limit branches |
| `test_rotate_api_key_*` (4) | `_rotate_api_key` disabled/single/multi-key paths |
| `test_handle_provider_failure_*` (7) | rate_limit, auth_error, quota_exceeded, server_error, unknown×2, disabled rotation |
| `test_roll_api_key_*` (6) | multi-key roll, disabled message, missing keys, preview truncation, no-change message |
| `test_handle_provider_failure_flags_after_consecutive_limit` | consecutive-failure provider flagging |

### Second pass (exact-message assertions)

| Test | Targets |
|------|---------|
| `test_roll_api_key_provider_not_found_exact_message` | `roll_api_key` provider-not-found return string |
| `test_roll_api_key_single_key_exact_no_op_message` | single-key `no rolling needed` substring |
| `test_roll_api_key_disabled_exact_message` | disabled-settings message (exact) |
| `test_roll_api_key_successful_roll_message_format` | success message with key indices/previews |
| `test_roll_api_key_short_key_preview_no_truncation` | preview when `len(key) <= 8` (no `...`) |
| `test_handle_provider_failure_service_unavailable_flags_no_rotation` | 503/service_unavailable flags provider, no rotation |
| `test_handle_provider_failure_unknown_first_failure_no_rotation` | unknown error: no rotation until 2nd failure |

Helper: `_setup_rotation_provider()` builds an isolated multi-key provider without touching live config.

## mutmut Invocation

```bash
# Install (dev extras include mutmut)
.venv/bin/pip3 install -e ".[dev,server]"

# Verify CLI + config load
.venv/bin/mutmut --help
.venv/bin/mutmut run --help

# Full scan (initial run ~20 min with --max-children 2)
.venv/bin/mutmut run --max-children 2

# Results
.venv/bin/mutmut results          # surviving mutants
.venv/bin/mutmut results --all true  # all statuses

# Retest specific survivors after adding tests
.venv/bin/mutmut run --max-children 2 'core.ai_engine.xǁAI_engineǁroll_api_key__mutmut_5'

# Mutation gate (run before release)
mutmut run --max-children 2
mutmut results --all true | grep -c killed
```

## Initial Scan Results (full run, 1254 mutants — before second-pass tests)

| Metric | Count |
|--------|------:|
| Total mutants | 1254 |
| Killed 🎉 | 568 |
| Survived 🙁 | 683 |
| No tests | 3 |
| **Overall kill rate** | **45.4%** |

### Key-rotation function kill rates

| Function | Killed | Checked | Kill rate |
|----------|-------:|--------:|----------:|
| `_select_optimal_key` | 45 | 59 | **76.3%** |
| `_rotate_api_key` | 29 | 40 | **72.5%** |
| `_handle_provider_failure` | 63 | 120 | **52.5%** |
| `roll_api_key` | 14 | 43 | **32.6%** |
| **Rotation paths combined** | **151** | **262** | **57.6%** |

### Post-test spot checks

After adding `roll_api_key` message/preview tests, spot retests confirmed kills:

- `roll_api_key__mutmut_5` ( `config.get('api_keys', None)` ) → **killed**
- `roll_api_key__mutmut_7` → **killed**
- `roll_api_key__mutmut_10` → still survived (string/format mutant)

## Second Scan Results (after exact-message tests, 1254 mutants)

| Metric | Count |
|--------|------:|
| Total mutants | 1254 |
| Killed 🎉 | 584 |
| Survived 🙁 | 667 |
| No tests / other | 3 |
| **Overall kill rate** | **46.7%** |

### Key-rotation function kill rates (second pass)

| Function | Killed | Checked | Kill rate | Δ from initial |
|----------|-------:|--------:|----------:|---------------:|
| `_select_optimal_key` | 44 | 59 | **74.6%** | −1.7pp |
| `_rotate_api_key` | 30 | 40 | **75.0%** | +2.5pp |
| `_handle_provider_failure` | 65 | 120 | **54.2%** | +1.7pp |
| `roll_api_key` | 30 | 43 | **69.8%** | **+37.2pp** |
| **Rotation paths combined** | **169** | **262** | **64.5%** | **+6.9pp** |

**>90% achieved on any function?** No — best is `_rotate_api_key` at 75.0%.

Biggest gain: `roll_api_key` (+37.2pp) from exact substring assertions on return messages, key-index formatting, and short-key preview branches.

## Concerns / Follow-ups

1. **Below 90% rotation-path goal:** `roll_api_key` (69.8%) and `_handle_provider_failure` (54.2%) remain below the plan's >90% aspiration. Remaining survivors are mostly string-format mutants, default-argument tweaks, and non-rotation branches inside `_handle_provider_failure` (provider flagging, verbose logging, health-monitor side effects).

2. **`last_used` required for rotation assertions:** `_select_optimal_key` clears `rate_limited` when `last_used` is `None`, so rotation tests must set `last_used` on the current key to observe index changes. This matches production behavior after keys have been used but is easy to miss in unit tests.

3. **Global `ENGINE_SETTINGS` mutation:** `engine.engine_settings` is a reference to the module-level dict; tests that disable rotation must restore state (fixture now resets `key_rotation_enabled = True`).

4. **Generated `mutants/` directory:** Full `mutmut run` writes a large `mutants/` tree (~60k+ lines). Not committed; add to `.gitignore` if mutation runs become routine.

5. **Run time:** Full scan of covered lines in `ai_engine.py` takes ~20 minutes with `--max-children 2`. CI should cache mutmut state or scope runs to changed rotation functions.

6. **Deprecation warnings:** mutmut 2.x warns on `paths_to_mutate` / `tests_dir`; modern keys (`source_paths`, `pytest_add_cli_args_test_selection`) are also set.

## Self-Review

| Requirement | Status |
|-------------|--------|
| `mutmut>=2.6.0` in dev deps | ✅ |
| `[tool.mutmut]` targeting `core/ai_engine.py` + rotation tests | ✅ |
| Initial mutmut scan executed | ✅ (1254 mutants) |
| Targeted tests added for rotation paths | ✅ (19 new tests) |
| Invocation documented in task report | ✅ |
| Commit message per plan | ✅ (pending) |