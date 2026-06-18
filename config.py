import os
from typing import Dict, List, Any, Optional, Tuple
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Load environment variables
load_dotenv()


class ProviderConfig(BaseModel):
    """Pydantic model for provider configuration validation"""
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

    @field_validator('method')
    @classmethod
    def validate_method(cls, v):
        if v not in ('GET', 'POST'):
            raise ValueError('method must be GET or POST')
        return v


class EngineSettings(BaseModel):
    """Pydantic model for engine settings validation"""
    default_timeout: int = Field(60, ge=1, le=300)
    max_retries: int = Field(3, ge=0, le=10)
    enable_auto_rotation: bool = True
    consecutive_failure_limit: int = Field(5, ge=1, le=100)
    key_rotation_enabled: bool = True
    provider_rotation_enabled: bool = True
    verbose_mode: bool = False


def validate_provider_configs(configs: Dict[str, Any]) -> Dict[str, Any]:
    """Validate all provider configs and return validated dict"""
    validated = {}
    for name, config in configs.items():
        try:
            validated[name] = ProviderConfig(**config).model_dump()
        except Exception as e:
            print(f"Warning: Provider '{name}' config invalid: {e}")
            validated[name] = config
    return validated


def validate_engine_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Validate engine settings"""
    try:
        known_fields = {k: v for k, v in settings.items() if k in EngineSettings.model_fields}
        validated = EngineSettings(**known_fields).model_dump()
        validated.update({k: v for k, v in settings.items() if k not in validated})
        return validated
    except Exception as e:
        print(f"Warning: ENGINE_SETTINGS validation failed: {e}")
        return settings


# AI Engine Configuration - Verified Working Free Providers
# Last verified: 2026-06-18
AI_CONFIGS = {
    # === VERIFIED WORKING (Tested 2026-06-18) ===
    "chi": {
        "id": 1, "priority": 1,
        "api_keys": [os.getenv("CHI_API_KEY"), os.getenv("CHI_API_KEY_2"), os.getenv("CHI_API_KEY_3")],
        "endpoint": "https://api.chatanywhere.tech/v1/chat/completions",
        "model_endpoint": "https://api.chatanywhere.tech/v1/models",
        "model_endpoint_auth": True, "model": "gpt-4.1-ca",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 4, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 80, "daily_limit": 1500,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "cerebras": {
        "id": 2, "priority": 2,
        "api_keys": [os.getenv("CEREBRAS_API_KEY"), os.getenv("CEREBRAS_API_KEY_2"), os.getenv("CEREBRAS_API_KEY_3")],
        "endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "model_endpoint": "https://api.cerebras.ai/v1/models",
        "model_endpoint_auth": True, "model": "llama-3.1-70b",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 4, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 60, "daily_limit": 2000,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "a3z": {
        "id": 3, "priority": 3,
        "api_keys": [None],
        "endpoint": "https://api.a3z.workers.dev/", "model_endpoint": None,
        "model_endpoint_auth": False, "model": "gpt-4.1-nano",
        "method": "GET", "auth_type": None, "max_tokens": None,
        "temperature": None, "timeout": 60, "retries": 3, "backoff": 1,
        "format": "a3z_get", "enabled": True, "rpm_limit": 30, "daily_limit": 500,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "groq": {
        "id": 4, "priority": 4,
        "api_keys": [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY_2"), os.getenv("GROQ_API_KEY_3")],
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "model_endpoint": "https://api.groq.com/openai/v1/models",
        "model_endpoint_auth": True, "model": "llama-3.3-70b-versatile",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 4, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 30, "daily_limit": 1000,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "openrouter": {
        "id": 5, "priority": 5,
        "api_keys": [os.getenv("OPENROUTER_API_KEY"), os.getenv("OPENROUTER_API_KEY_2"), os.getenv("OPENROUTER_API_KEY_3")],
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "model_endpoint": "https://openrouter.ai/api/v1/models",
        "model_endpoint_auth": True, "model": "meta-llama/llama-3.1-405b-instruct:free",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4000,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 25, "daily_limit": 400,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "nvidia": {
        "id": 6, "priority": 6,
        "api_keys": [os.getenv("NVIDIA_API_KEY"), os.getenv("NVIDIA_API_KEY_2"), os.getenv("NVIDIA_API_KEY_3")],
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model_endpoint": "https://integrate.api.nvidia.com/v1/models",
        "model_endpoint_auth": True, "model": "deepseek-ai/deepseek-r1",
        "method": "POST", "auth_type": "bearer", "max_tokens": 512,
        "temperature": 1.0, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 30, "daily_limit": 500,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "vercel": {
        "id": 7, "priority": 7,
        "api_keys": [os.getenv("VERCEL_API_KEY"), os.getenv("VERCEL_API_KEY_2"), os.getenv("VERCEL_API_KEY_3")],
        "endpoint": "https://ai-gateway.vercel.sh/v1/chat/completions",
        "model_endpoint": "https://ai-gateway.vercel.sh/v1/models",
        "model_endpoint_auth": True, "model": "anthropic/claude-sonnet-4",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4000,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 15, "daily_limit": 150,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "github": {
        "id": 8, "priority": 8,
        "api_keys": [os.getenv("GITHUB_API_KEY"), os.getenv("GITHUB_API_KEY_2"), os.getenv("GITHUB_API_KEY_3")],
        "endpoint": "https://models.github.ai/inference/chat/completions",
        "model_endpoint": "https://models.github.ai/inference/models",
        "model_endpoint_auth": True, "model": "openai/gpt-4o",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4000,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 15, "daily_limit": 150,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "flowith": {
        "id": 9, "priority": 9,
        "api_keys": [os.getenv("FLOWITH_API_KEY"), os.getenv("FLOWITH_API_KEY_2"), os.getenv("FLOWITH_API_KEY_3")],
        "endpoint": "https://edge.flowith.net/external/use/seek-knowledge",
        "model_endpoint": None, "model_endpoint_auth": False, "model": "gpt-4o-mini",
        "method": "POST", "auth_type": "bearer", "max_tokens": 2048,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "flowith", "enabled": True, "rpm_limit": 10, "daily_limit": 100,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "cloudflare": {
        "id": 10, "priority": 10,
        "api_keys": [os.getenv("CLOUDFLARE_API_KEY"), os.getenv("CLOUDFLARE_API_KEY_2"), os.getenv("CLOUDFLARE_API_KEY_3")],
        "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        "endpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions",
        "model_endpoint": None, "model_endpoint_auth": False,
        "model": "@cf/meta/llama-3.1-8b-instruct",
        "method": "POST", "auth_type": "bearer", "max_tokens": None,
        "temperature": 1, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "cloudflare", "enabled": True, "rpm_limit": 100, "daily_limit": 2000,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "minimax": {
        "id": 11, "priority": 11,
        "api_keys": [os.getenv("MINIMAX_API_KEY"), os.getenv("MINIMAX_API_KEY_2"), os.getenv("MINIMAX_API_KEY_3")],
        "endpoint": "https://api.minimaxi.chat/v1/text/chatcompletion_v2",
        "model_endpoint": None, "model_endpoint_auth": False,
        "model": "minimax-reasoning-01",
        "method": "POST", "auth_type": "bearer", "max_tokens": 40000,
        "temperature": 1.0, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "minimax", "enabled": True, "rpm_limit": 5, "daily_limit": 50,
        "current_key_index": 0, "consecutive_failures": 0
    },

    # === NEW FREE PROVIDERS (Verified 2026-06-18) ===
    "electronhub": {
        "id": 12, "priority": 12,
        "api_keys": [os.getenv("ELECTRONHUB_API_KEY"), os.getenv("ELECTRONHUB_API_KEY_2")],
        "endpoint": "https://api.electronhub.ai/v1/chat/completions",
        "model_endpoint": "https://api.electronhub.ai/v1/models",
        "model_endpoint_auth": True, "model": "gpt-4o",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 30, "daily_limit": 500,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "nagaai": {
        "id": 13, "priority": 13,
        "api_keys": [os.getenv("NAGAAI_API_KEY"), os.getenv("NAGAAI_API_KEY_2")],
        "endpoint": "https://api.naga.ac/v1/chat/completions",
        "model_endpoint": "https://api.naga.ac/v1/models",
        "model_endpoint_auth": True, "model": "claude-3.5-sonnet",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 30, "daily_limit": 500,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "navyapi": {
        "id": 14, "priority": 14,
        "api_keys": [os.getenv("NAVY_API_KEY"), os.getenv("NAVY_API_KEY_2")],
        "endpoint": "https://api.navy/v1/chat/completions",
        "model_endpoint": "https://api.navy/v1/models",
        "model_endpoint_auth": True, "model": "gpt-4o",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 30, "daily_limit": 500,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "zanityai": {
        "id": 15, "priority": 15,
        "api_keys": [os.getenv("ZANITY_API_KEY"), os.getenv("ZANITY_API_KEY_2")],
        "endpoint": "https://api.zanity.xyz/v1/chat/completions",
        "model_endpoint": "https://api.zanity.xyz/v1/models",
        "model_endpoint_auth": True, "model": "gpt-4o",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 30, "daily_limit": 500,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "voidai": {
        "id": 16, "priority": 16,
        "api_keys": [os.getenv("VOIDAI_API_KEY"), os.getenv("VOIDAI_API_KEY_2")],
        "endpoint": "https://api.voidai.app/v1/chat/completions",
        "model_endpoint": "https://api.voidai.app/v1/models",
        "model_endpoint_auth": True, "model": "gpt-4o",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 30, "daily_limit": 500,
        "current_key_index": 0, "consecutive_failures": 0
    },
    "mnnai": {
        "id": 17, "priority": 17,
        "api_keys": [os.getenv("MNN_API_KEY"), os.getenv("MNN_API_KEY_2")],
        "endpoint": "https://api.mnnai.ru/v1/chat/completions",
        "model_endpoint": "https://api.mnnai.ru/v1/models",
        "model_endpoint_auth": True, "model": "gpt-4o",
        "method": "POST", "auth_type": "bearer", "max_tokens": 4096,
        "temperature": 0.7, "timeout": 60, "retries": 3, "backoff": 5,
        "format": "openai", "enabled": True, "rpm_limit": 30, "daily_limit": 500,
        "current_key_index": 0, "consecutive_failures": 0
    },

    # === LOCAL/OPTIONAL ===
    "offline": {
        "id": 18, "priority": 20,
        "api_keys": [None],
        "endpoint": "http://localhost:11434/api/generate",
        "model_endpoint": "http://localhost:11434/api/tags",
        "model_endpoint_auth": False, "model": "llama2",
        "method": "POST", "auth_type": None, "max_tokens": None,
        "temperature": None, "timeout": 60, "retries": 3, "backoff": 2,
        "format": "ollama", "enabled": False,
        "rpm_limit": 100, "daily_limit": 1000,
        "current_key_index": 0, "consecutive_failures": 0
    }
}

# Global Engine Settings
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

# Autodecide Configuration
AUTODECIDE_CONFIG = {
    "enabled": True,
    "cache_duration": 1800,
    "model_cache": {}
}

# Config version for tracking
CONFIG_VERSION = "4.0.0"

# Hot-reload support
_config_last_modified = 0

def check_config_reload():
    """Check if config file has been modified and reload if needed"""
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
    """Get summary of current configuration"""
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
    """Print message only if verbose mode is enabled"""
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
