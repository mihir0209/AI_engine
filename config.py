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

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        valid_formats = {
            "openai",
            "gemini",
            "cohere",
            "a3z_get",
            "cloudflare",
            "ollama",
            "flowith",
            "minimax",
        }
        if v not in valid_formats:
            raise ValueError(f"format must be one of {valid_formats}")
        return v


class EngineSettings(BaseModel):
    default_timeout: int = Field(60, ge=1, le=300)
    max_retries: int = Field(3, ge=0, le=10)
    enable_auto_rotation: bool = True
    consecutive_failure_limit: int = Field(5, ge=1, le=100)
    key_rotation_enabled: bool = True
    provider_rotation_enabled: bool = True
    verbose_mode: bool = False


# AI Engine Configuration - Free Providers Only
# Last verified: 2026-06-18
#
# PROVIDER STRATEGY:
# 1. Self-hosted (g4f, Ollama) - TRULY FREE
# 2. Free tier APIs with generous limits
# 3. Custom providers added via CLI

AI_CONFIGS = {
    # === SELF-HOSTED (TRULY FREE) ===
    "g4f": {
        "id": 1,
        "priority": 3,
        "api_keys": [None],
        "endpoint": os.getenv(
            "G4F_ENDPOINT", "http://localhost:8080/v1/chat/completions"
        ),
        "model_endpoint": os.getenv(
            "G4F_MODELS_ENDPOINT", "http://localhost:8080/v1/models"
        ),
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
        "enabled": False,  # Disabled - enable when g4f is running
        "rpm_limit": None,
        "daily_limit": None,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    "ollama": {
        "id": 2,
        "priority": 5,
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
        "enabled": False,
        "rpm_limit": None,
        "daily_limit": None,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    # === FREE TIER APIs (generous limits) ===
    "groq": {
        "id": 3,
        "priority": 2,
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
        "consecutive_failures": 0,
    },
    "openrouter": {
        "id": 4,
        "priority": 3,
        "api_keys": [os.getenv("OPENROUTER_API_KEY")],
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "model_endpoint": "https://openrouter.ai/api/v1/models",
        "model_endpoint_auth": True,
        "model": "google/gemma-4-26b-a4b-it:free",
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
        "consecutive_failures": 0,
    },
    "gemini": {
        "id": 5,
        "priority": 4,
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
        "consecutive_failures": 0,
    },
    "nvidia": {
        "id": 6,
        "priority": 4,
        "api_keys": [os.getenv("NVIDIA_API_KEY")],
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model_endpoint": "https://integrate.api.nvidia.com/v1/models",
        "model_endpoint_auth": True,
        "model": "meta/llama-3.1-8b-instruct",
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
        "consecutive_failures": 0,
    },
    "cerebras": {
        "id": 7,
        "priority": 5,
        "api_keys": [os.getenv("CEREBRAS_API_KEY")],
        "endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "model_endpoint": "https://api.cerebras.ai/v1/models",
        "model_endpoint_auth": True,
        "model": "zai-glm-4.7",
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
        "consecutive_failures": 0,
    },
    "cloudflare": {
        "id": 8,
        "priority": 6,
        "api_keys": [os.getenv("CLOUDFLARE_API_KEY")],
        "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        "endpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
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
        "enabled": bool(
            os.getenv("CLOUDFLARE_API_KEY") and os.getenv("CLOUDFLARE_ACCOUNT_ID")
        ),
        "rpm_limit": 100,
        "daily_limit": 10000,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    "github": {
        "id": 9,
        "priority": 3,
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
        "consecutive_failures": 0,
    },
    "vercel": {
        "id": 10,
        "priority": 7,
        "api_keys": [os.getenv("VERCEL_API_KEY")],
        "endpoint": "https://ai-gateway.vercel.sh/v1/chat/completions",
        "model_endpoint": "https://ai-gateway.vercel.sh/v1/models",
        "model_endpoint_auth": True,
        "model": "moonshotai/kimi-k2.5",
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
        "consecutive_failures": 0,
    },
    "freetheai": {
        "id": 11,
        "priority": 2,
        "api_keys": [os.getenv("FREETHEAI_API_KEY")],
        "endpoint": "https://api.freetheai.xyz/v1/chat/completions",
        "model_endpoint": "https://api.freetheai.xyz/v1/models",
        "model_endpoint_auth": True,
        "model": "glm/glm-4.7",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout": 20,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("FREETHEAI_API_KEY")) if True else False,
        "rpm_limit": 10,
        "daily_limit": 250,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    "hcnsec": {
        "id": 12,
        "priority": 2,
        "api_keys": [os.getenv("HCNSEC_API_KEY")],
        "endpoint": "https://api.iamhc.cn/v1/chat/completions",
        "model_endpoint": "https://api.iamhc.cn/v1/models",
        "model_endpoint_auth": True,
        "model": "Kimi-K2.6",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout": 20,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("HCNSEC_API_KEY")) if True else False,
        "rpm_limit": None,
        "daily_limit": None,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    "mimo": {
        "id": 13,
        "priority": 1,
        "api_keys": [os.getenv("MIMO_API_KEY")],
        "endpoint": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        "model_endpoint": "https://token-plan-cn.xiaomimimo.com/v1/models",
        "model_endpoint_auth": True,
        "model": "mimo-v2.5",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout": 20,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("MIMO_API_KEY")) if True else False,
        "rpm_limit": None,
        "daily_limit": None,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    "llm7": {
        "id": 14,
        "priority": 2,
        "api_keys": [os.getenv("LLM7_API_KEY")],
        "endpoint": "https://api.llm7.io/v1/chat/completions",
        "model_endpoint": "https://api.llm7.io/v1/models",
        "model_endpoint_auth": True,
        "model": "default",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout": 20,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": bool(os.getenv("LLM7_API_KEY")) if True else False,
        "rpm_limit": 40,
        "daily_limit": 2400,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    # === VERIFIED FREE PROVIDERS (No API Key Required) ===
    # g4f.space Groq - Free, no auth
    "g4f_groq": {
        "id": 15,
        "priority": 3,
        "api_keys": ["free"],
        "endpoint": "https://g4f.space/api/groq/chat/completions",
        "model_endpoint": "https://g4f.space/api/groq/models",
        "model_endpoint_auth": False,
        "model": "llama-3.3-70b-versatile",
        "method": "POST",
        "auth_type": None,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 30,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 10,
        "daily_limit": 100,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    # g4f.space Gemini - Free, no auth
    "g4f_gemini": {
        "id": 16,
        "priority": 3,
        "api_keys": ["free"],
        "endpoint": "https://g4f.space/api/gemini/chat/completions",
        "model_endpoint": "https://g4f.space/api/gemini/models",
        "model_endpoint_auth": False,
        "model": "models/gemini-2.5-flash",
        "method": "POST",
        "auth_type": None,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 30,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 10,
        "daily_limit": 100,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    # g4f.space Ollama - Free, no auth
    "g4f_ollama": {
        "id": 17,
        "priority": 4,
        "api_keys": ["free"],
        "endpoint": "https://g4f.space/api/ollama/chat/completions",
        "model_endpoint": "https://g4f.space/api/ollama/models",
        "model_endpoint_auth": False,
        "model": "gpt-oss:20b",
        "method": "POST",
        "auth_type": None,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 30,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 10,
        "daily_limit": 100,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    # g4f.space Pollinations - Free, no auth
    "g4f_pollinations": {
        "id": 18,
        "priority": 5,
        "api_keys": ["free"],
        "endpoint": "https://g4f.space/api/pollinations/chat/completions",
        "model_endpoint": "https://g4f.space/api/pollinations/models",
        "model_endpoint_auth": False,
        "model": "openai",
        "method": "POST",
        "auth_type": None,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 30,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 10,
        "daily_limit": 100,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    # g4f.space Nvidia - Free, no auth
    "g4f_nvidia": {
        "id": 19,
        "priority": 9,
        "api_keys": ["free"],
        "endpoint": "https://g4f.space/api/nvidia/chat/completions",
        "model_endpoint": "https://g4f.space/api/nvidia/models",
        "model_endpoint_auth": False,
        "model": "nvidia/nemotron-3-nano-30b-a3b",
        "method": "POST",
        "auth_type": None,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 30,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 10,
        "daily_limit": 100,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    # UncloseAI Hermes - Free, no auth required
    "hermes": {
        "id": 20,
        "priority": 7,
        "api_keys": ["free"],
        "endpoint": "https://hermes.ai.unturf.com/v1/chat/completions",
        "model_endpoint": "https://hermes.ai.unturf.com/v1/models",
        "model_endpoint_auth": True,
        "model": "adamo1139/Hermes-3-Llama-3.1-8B-FP8-Dynamic",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout": 30,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 10,
        "daily_limit": 100,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    # Pollinations AI - Free, no auth required
    "pollinations": {
        "id": 21,
        "priority": 2,
        "api_keys": ["free"],
        "endpoint": "https://text.pollinations.ai/openai",
        "model_endpoint": None,
        "model_endpoint_auth": False,
        "model": "openai",
        "method": "POST",
        "auth_type": None,
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 30,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 10,
        "daily_limit": 100,
        "current_key_index": 0,
        "consecutive_failures": 0,
    },
    "paxsenix": {
        "id": 3,
        "priority": 3,
        "api_keys": [os.getenv("PAXSENIX_API_KEY"), os.getenv("PAXSENIX_API_KEY_2"), os.getenv("PAXSENIX_API_KEY_3")],
        "endpoint": "https://api.paxsenix.org/v1/chat/completions",
        "model_endpoint": "https://api.paxsenix.org/v1/models",
        "model_endpoint_auth": True,
        "model": "deepseek-r1",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 5,
        "backoff": 25,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 25,
        "daily_limit": 1000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
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
        "expected_keywords": ["test successful", "ai engine", "v3.0", "working"],
    },
    "priority_settings": {
        "enable_dynamic_priority": True,
        "success_rate_weight": 0.4,
        "response_time_weight": 0.3,
        "cost_weight": 0.2,
        "reliability_weight": 0.1,
        "rerank_interval_hours": 24,
    },
}

AUTODECIDE_CONFIG = {"enabled": True, "cache_duration": 1800, "model_cache": {}}
CONFIG_VERSION = "6.0.0"
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
    enabled_count = sum(1 for c in AI_CONFIGS.values() if c.get("enabled", True))
    total_keys = sum(
        len([k for k in c.get("api_keys", []) if k]) for c in AI_CONFIGS.values()
    )
    return {
        "version": CONFIG_VERSION,
        "total_providers": len(AI_CONFIGS),
        "enabled_providers": enabled_count,
        "disabled_providers": len(AI_CONFIGS) - enabled_count,
        "total_api_keys": total_keys,
        "engine_settings": ENGINE_SETTINGS,
        "autodecide_enabled": AUTODECIDE_CONFIG.get("enabled", True),
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
            safe_message = message.encode("ascii", "replace").decode("ascii")
            print(safe_message)
