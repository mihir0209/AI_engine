"""Shim — canonical provider config is ``core.config``.

Editable installs and scripts may ``from config import AI_CONFIGS``; this re-exports
``core.config`` so there is a single source of truth.
"""

from core.config import *  # noqa: F403
