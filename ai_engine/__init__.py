"""AI Synapse SDK — Drop-in OpenAI & Anthropic compatibility with free multi-provider routing."""

from ._version import get_version

__version__ = get_version()

from .openai import OpenAI, AsyncOpenAI
from .anthropic import Anthropic, AsyncAnthropic
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


def use(**kwargs):
    """Configure global AI Engine settings (late configuration)."""
    _global_config.update(kwargs)
