"""AI Engine SDK — Drop-in OpenAI & Anthropic compatibility with free multi-provider routing."""

__version__ = "4.0.0"

from .openai import OpenAI, AsyncOpenAI
from ._engine import get_engine, set_engine, AIEngine
from ._exceptions import (
    AIEngineError,
    OpenAIError,
    BadRequestError,
    AuthenticationError,
    RateLimitError,
    InternalServerError,
    NotFoundError,
)

# Lazy Anthropic import (not implemented yet)
try:
    from .anthropic import Anthropic, AsyncAnthropic
except ImportError:
    pass

def use(**kwargs):
    """Configure global AI Engine settings (late configuration)."""
    from ._engine import _global_config
    _global_config.update(kwargs)
