"""AI Synapse SDK — Drop-in OpenAI & Anthropic compatibility with free multi-provider routing."""

__version__ = "4.0.7"

from .openai import OpenAI, AsyncOpenAI
from ._engine import AIEngine, get_engine, set_engine, _global_config
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
    _global_config.update(kwargs)
