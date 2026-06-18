import os
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, ConfigDict

load_dotenv()


class ProviderConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: int
    priority: int = Field(ge=1, le=100)
    api_keys: List[Optional[str]] = []
    endpoint: str
    model_endpoint: Optional[str] = None
    model_endpoint_auth: bool = True
    model: str
    method: str = "POST"
    auth_type: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)
    timeout: int = Field(60, ge=1, le=300)
    retries: int = Field(3, ge=0, le=10)
    backoff: int = Field(5, ge=0, le=60)
    format: str = "openai"
    enabled: bool = True
    rpm_limit: Optional[int] = None
    daily_limit: Optional[int] = None
    current_key_index: int = 0
    consecutive_failures: int = 0

    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        valid_formats = {'openai', 'gemini', 'cohere', 'a3z_get', 'cloudflare', 'ollama', 'flowith', 'minimax'}
        if v not in valid_formats:
            raise ValueError(f'format must be one of {valid_formats}')
        return v


class EngineSettings(BaseModel):
    default_timeout: int = Field(60, ge=1, le=300)
    max_retries: int = Field(3, ge=0, le=10)
    enable_auto_rotation: bool = True
    consecutive_failure_limit: int = Field(5, ge=1, le=100)
    key_rotation_enabled: bool = True
    provider_rotation_enabled: bool = True
    verbose_mode: bool = False


# AI Engine Configuration - Free/Generous Free-Tier Providers Only
# Last verified: 2026-06-18
#
# PROVIDER STRATEGY:
# 1. Self-hosted g4f server (recommended) - truly free, no limits
# 2. Providers with generous free tiers (need API key but free quota)
# 3. Local Ollama for offline use
#
# To use g4f: docker run -p 8080:8080 hlohaus789/g4f
# Then set G4F_ENDPOINT=http://localhost:8080/v1 in .env

AI_CONFIGS = {
    # === SELF-HOSTED GPT4FREE (TRULY FREE - RECOMMENDED) ===
    # Run: docker run -p 8080:8080 hlohaus789/g4f
    # Or install: pip install g4f && python -m g4f
    "g4f": {
        "id": 1,
        "priority": 1,  # Highest priority - truly free
        "api_keys": [None],  # No API key needed
        "endpoint": os.getenv("G4F_ENDPOINT", "http://localhost:8080/v1/chat/completions"),
        "model_endpoint": os.getenv("G4F_MODELS_ENDPOINT", "http://localhost:8080/v1/models"),
        "model_endpoint_auth": False,
        "model": "gpt-4o",
        "method": "POST",
        "auth_type": None,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 120,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": None,  # No limit
        "daily_limit": None,  # No limit
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # === LOCAL OLLAMA (FREE - NEEDS OLLAMA INSTALLED) ===
    # Install: curl -fsSL https://ollama.com/install.sh | sh
    # Then: ollama pull llama3.1
    "ollama": {
        "id": 2,
        "priority": 2,
        "api_keys": [None],
        "endpoint": "http://localhost:11434/api/generate",
        "model_endpoint": "http://localhost:11434/api/tags",
        "model_endpoint_auth": False,
        "model": "llama3.1",
        "method": "POST",
        "auth_type": None,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 120,
        "retries": 3,
        "backoff": 2,
        "format": "ollama",
        "enabled": False,  # Enable if Ollama is installed
        "rpm_limit": None,
        "daily_limit": None,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # === PROVIDERS WITH FREE TIERS (need API key but have free quota) ===

    # Groq - Free tier: 30 RPM, 14,400 RPD
    # Sign up: https://console.groq.com
    "groq": {
        "id": 3,
        "priority": 3,
        "api_keys": [os.getenv("GROQ_API_KEY")],
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "model_endpoint": "https://api.groq.com/openai/v1/models",
        "model_endpoint_auth": True,
        "model": "llama-3.3-70b-versatile",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 4,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("GROQ_API_KEY")),
        "rpm_limit": 30,
        "daily_limit": 14400,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # SambaNova - Free tier: generous daily limits
    # Sign up: https://cloud.sambanova.ai
    "sambanova": {
        "id": 4,
        "priority": 4,
        "api_keys": [os.getenv("SAMBANOVA_API_KEY")],
        "endpoint": "https://api.sambanova.ai/v1/chat/completions",
        "model_endpoint": "https://api.sambanova.ai/v1/models",
        "model_endpoint_auth": True,
        "model": "Meta-Llama-3.3-70B-Instruct",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("SAMBANOVA_API_KEY")),
        "rpm_limit": 20,
        "daily_limit": 1000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # Together AI - Free tier: $1 credit on signup
    # Sign up: https://api.together.xyz
    "together": {
        "id": 5,
        "priority": 5,
        "api_keys": [os.getenv("TOGETHER_API_KEY")],
        "endpoint": "https://api.together.xyz/v1/chat/completions",
        "model_endpoint": "https://api.together.xyz/v1/models",
        "model_endpoint_auth": True,
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("TOGETHER_API_KEY")),
        "rpm_limit": 60,
        "daily_limit": 1000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # DeepInfra - Free tier: $1 credit on signup
    # Sign up: https://deepinfra.com
    "deepinfra": {
        "id": 6,
        "priority": 6,
        "api_keys": [os.getenv("DEEPINFRA_API_KEY")],
        "endpoint": "https://api.deepinfra.com/v1/openai/chat/completions",
        "model_endpoint": "https://api.deepinfra.com/v1/openai/models",
        "model_endpoint_auth": True,
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("DEEPINFRA_API_KEY")),
        "rpm_limit": 60,
        "daily_limit": 1000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # OpenRouter - Free tier: 200 free credits on signup
    # Sign up: https://openrouter.ai
    # Use free models: model:free suffix
    "openrouter": {
        "id": 7,
        "priority": 7,
        "api_keys": [os.getenv("OPENROUTER_API_KEY")],
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "model_endpoint": "https://openrouter.ai/api/v1/models",
        "model_endpoint_auth": True,
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("OPENROUTER_API_KEY")),
        "rpm_limit": 20,
        "daily_limit": 200,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # NVIDIA NIM - Free tier: 1000 credits/month
    # Sign up: https://build.nvidia.com
    "nvidia": {
        "id": 8,
        "priority": 8,
        "api_keys": [os.getenv("NVIDIA_API_KEY")],
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model_endpoint": "https://integrate.api.nvidia.com/v1/models",
        "model_endpoint_auth": True,
        "model": "deepseek-ai/deepseek-r1",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 512,
        "temperature": 1.0,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("NVIDIA_API_KEY")),
        "rpm_limit": 30,
        "daily_limit": 500,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # Cerebras - Free tier: 30 RPM
    # Sign up: https://cloud.cerebras.ai
    "cerebras": {
        "id": 9,
        "priority": 9,
        "api_keys": [os.getenv("CEREBRAS_API_KEY")],
        "endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "model_endpoint": "https://api.cerebras.ai/v1/models",
        "model_endpoint_auth": True,
        "model": "llama-3.3-70b",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 4,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("CEREBRAS_API_KEY")),
        "rpm_limit": 30,
        "daily_limit": 1000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # Cloudflare Workers AI - Free tier: 10,000 neurons/day
    # Sign up: https://dash.cloudflare.com
    "cloudflare": {
        "id": 10,
        "priority": 10,
        "api_keys": [os.getenv("CLOUDFLARE_API_KEY")],
        "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        "endpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions",
        "model_endpoint": None,
        "model_endpoint_auth": False,
        "model": "@cf/meta/llama-3.1-8b-instruct",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": None,
        "temperature": 1,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "cloudflare",
        "enabled": bool(os.getenv("CLOUDFLARE_API_KEY") and os.getenv("CLOUDFLARE_ACCOUNT_ID")),
        "rpm_limit": 100,
        "daily_limit": 10000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # Google Gemini - Free tier: 15 RPM, 1M tokens/day
    # Sign up: https://aistudio.google.com
    "gemini": {
        "id": 11,
        "priority": 11,
        "api_keys": [os.getenv("GEMINI_API_KEY")],
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        "model_endpoint": None,
        "model_endpoint_auth": False,
        "model": "gemini-2.0-flash",
        "method": "POST",
        "auth_type": "query_param",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 4,
        "backoff": 5,
        "format": "gemini",
        "enabled": bool(os.getenv("GEMINI_API_KEY")),
        "rpm_limit": 15,
        "daily_limit": 1500,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # GitHub Models - Free tier: 15 RPM
    # Sign up: https://github.com/marketplace/models
    "github": {
        "id": 12,
        "priority": 12,
        "api_keys": [os.getenv("GITHUB_API_KEY")],
        "endpoint": "https://models.github.ai/inference/chat/completions",
        "model_endpoint": "https://models.github.ai/inference/models",
        "model_endpoint_auth": True,
        "model": "openai/gpt-4o-mini",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("GITHUB_API_KEY")),
        "rpm_limit": 15,
        "daily_limit": 150,
        "current_key_index": 0,
        "consecutive_failures": 0
    },

    # Vercel AI Gateway - Free tier available
    "vercel": {
        "id": 13,
        "priority": 13,
        "api_keys": [os.getenv("VERCEL_API_KEY")],
        "endpoint": "https://ai-gateway.vercel.sh/v1/chat/completions",
        "model_endpoint": "https://ai-gateway.vercel.sh/v1/models",
        "model_endpoint_auth": True,
        "model": "anthropic/claude-sonnet-4",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("VERCEL_API_KEY")),
        "rpm_limit": 15,
        "daily_limit": 150,
        "current_key_index": 0,
        "consecutive_failures": 0
    }
}


ENGINE_SETTINGS = {
    "default_timeout": 60,
    "max_retries": 3,
    "enable_auto_rotation": True,
    "consecutive_failure_limit": 5,
    "key_rotation_enabled": True,
    "provider_rotation_enabled": True,
    "verbose_mode": False,
    "stress_test_settings": {
        "min_pass_percentage": 75,
        "test_iterations": 3,
        "test_timeout": 30,
        "concurrent_tests": 2,
        "test_prompt": "Hello! Please respond with exactly: 'Test successful - AI Engine v3.0 working!'",
        "expected_keywords": ["test successful", "ai engine", "v3.0", "working"]
    },
    "priority_settings": {
        "enable_dynamic_priority": True,
        "success_rate_weight": 0.4,
        "response_time_weight": 0.3,
        "cost_weight": 0.2,
        "reliability_weight": 0.1,
        "rerank_interval_hours": 24
    }
}

AUTODECIDE_CONFIG = {
    "enabled": True,
    "cache_duration": 1800,
    "model_cache": {}
}

CONFIG_VERSION = "5.0.0"

_config_last_modified = 0


def check_config_reload():
    global _config_last_modified, AI_CONFIGS, ENGINE_SETTINGS
    try:
        import config as _config_module
        import importlib
        current_modified = os.path.getmtime(_config_module.__file__)
        if current_modified > _config_last_modified and _config_last_modified > 0:
            verbose_print("Config file changed, reloading...")
            importlib.reload(_config_module)
            AI_CONFIGS = _config_module.AI_CONFIGS
            ENGINE_SETTINGS = _config_module.ENGINE_SETTINGS
            verbose_print("Config reloaded successfully")
        _config_last_modified = current_modified
    except Exception as e:
        verbose_print(f"Config reload check failed: {e}")


def get_config_summary() -> Dict[str, Any]:
    enabled_count = sum(1 for c in AI_CONFIGS.values() if c.get('enabled', True))
    total_keys = sum(len([k for k in c.get('api_keys', []) if k]) for c in AI_CONFIGS.values())
    return {
        'version': CONFIG_VERSION,
        'total_providers': len(AI_CONFIGS),
        'enabled_providers': enabled_count,
        'disabled_providers': len(AI_CONFIGS) - enabled_count,
        'total_api_keys': total_keys,
        'engine_settings': ENGINE_SETTINGS,
        'autodecide_enabled': AUTODECIDE_CONFIG.get('enabled', True)
    }


def verbose_print(message: str, verbose_override: bool = None):
    if verbose_override is not None:
        is_verbose = verbose_override
    else:
        is_verbose = ENGINE_SETTINGS.get("verbose_mode", False)
    if is_verbose:
        try:
            print(message)
        except UnicodeEncodeError:
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            print(safe_message)
