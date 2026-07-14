"""Legacy server entry — canonical FastAPI app is ``ai_engine.server.app``.

Use ``python -m ai_engine serve`` or ``from ai_engine.server.app import app``.
"""

from ai_engine.server.app import app, main

__all__ = ["app", "main"]

if __name__ == "__main__":
    main()
