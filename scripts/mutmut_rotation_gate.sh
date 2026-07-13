#!/usr/bin/env bash
# Requires a completed local run: mutmut run (see CONTRIBUTING.md).
set -euo pipefail
THRESHOLD="${1:-90}"
export MUTMUT_ROTATION_THRESHOLD="$THRESHOLD"
python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

p = Path("mutants/core/ai_engine.py.meta")
if not p.exists():
    print("missing mutants/core/ai_engine.py.meta — run: mutmut run", file=sys.stderr)
    sys.exit(2)

codes = json.loads(p.read_text())["exit_code_by_key"]
rot = (
    "_rotate_api_key",
    "_select_optimal_key",
    "_handle_provider_failure",
    "_request_with_key_rotation",
    "roll_api_key",
)
rc = {k: v for k, v in codes.items() if any(f in k for f in rot) and v in (0, 1)}
killed = sum(1 for v in rc.values() if v == 1)
total = len(rc)
if total == 0:
    print("no rotation mutants evaluated", file=sys.stderr)
    sys.exit(2)

thresh = float(os.environ["MUTMUT_ROTATION_THRESHOLD"])
pct = 100 * killed / total
print(f"rotation chain: {killed}/{total} = {pct:.1f}% (threshold {thresh}%)")
sys.exit(0 if pct >= thresh else 1)
PY