"""Single source of truth for package version (reads pyproject.toml in dev)."""
from __future__ import annotations

import re
from pathlib import Path


def _read_pyproject_version() -> str | None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not pyproject.is_file():
        return None
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else None


def get_version() -> str:
    # Prefer pyproject.toml in a source checkout (editable installs may lag).
    from_dev = _read_pyproject_version()
    if from_dev:
        return from_dev
    try:
        from importlib.metadata import version

        return version("ai-synapse")
    except Exception:
        return "0.0.0"