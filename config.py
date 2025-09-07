import os
from typing import Dict, List, Any, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AI Engine Configuration - All 22 Providers with multiple API keys for rotation
AI_CONFIGS = {
    "a4f": {
        "id": 1,
        "priority": 5,
        "api_keys": [
            os.getenv("A4F_API_KEY"),
            os.getenv("A4F_API_KEY_2"),
            os.getenv("A4F_API_KEY_3"),
        ],
        "endpoint": "https://api.a4f.co/v1/chat/completions",
        "model_endpoint": "https://api.a4f.co/v1/models",
        "model_endpoint_auth": True,
        "model": "provider-3/llama-3.1-70b",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": None,
        "temperature": None,
        "timeout": 60,
        "retries": 5,
        "backoff": 25,
        "format": "openai",
        "enabled": True,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "chi": {
        "id": 2,
        "priority": 2,
        "api_keys": [
            os.getenv("CHI_API_KEY"),
            os.getenv("CHI_API_KEY_2"),
            os.getenv("CHI_API_KEY_3"),
        ],
        "endpoint": "https://api.chatanywhere.tech/v1/chat/completions",
        "model_endpoint": "https://api.chatanywhere.tech/v1/models",
        "model_endpoint_auth": True,
        "model": "gpt-4.1-mini",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 4,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 80,
        "daily_limit": 1500,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "paxsenix": {
        "id": 3,
        "priority": 1,
        "api_keys": [
            os.getenv("PAXSENIX_API_KEY"),
            os.getenv("PAXSENIX_API_KEY_2"),
            os.getenv("PAXSENIX_API_KEY_3"),
        ],
        "endpoint": "https://api.paxsenix.biz.id/v1/chat/completions",
        "model_endpoint": "https://api.paxsenix.biz.id/v1/models",
        "model_endpoint_auth": True,
        "model": "claude-3-7-sonnet",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": None,
        "temperature": None,
        "timeout": 60,
        "retries": 5,
        "backoff": 25,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 120,
        "daily_limit": 2500,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "mango": {
        "id": 4,
        "priority": 6,
        "api_keys": [
            os.getenv("MANGO_API_KEY"),
            os.getenv("MANGO_API_KEY_2"),
            os.getenv("MANGO_API_KEY_3"),
        ],
        "endpoint": "https://api.mangoi.in/v1/chat/completions",
        "model_endpoint": "https://api.mangoi.in/v1/models",
        "model_endpoint_auth": True,
        "model": "gpt-4.1-mini",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": None,
        "temperature": None,
        "timeout": 60,
        "retries": 5,
        "backoff": 25,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 40,
        "daily_limit": 600,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "samurai": {
        "id": 5,
        "priority": 4,
        "api_keys": [
            os.getenv("SAMURAI_API_KEY"),
            os.getenv("SAMURAI_API_KEY_2"),
            os.getenv("SAMURAI_API_KEY_3"),
        ],
        "endpoint": "https://samuraiapi.in/v1/chat/completions",
        "model_endpoint": "https://samuraiapi.in/v1/models",
        "model_endpoint_auth": True,
        "model": "gpt-4.1-mini",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 7,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 50,
        "daily_limit": 800,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "typegpt": {
        "id": 6,
        "priority": 8,
        "api_keys": [
            os.getenv("WOW_TYPEGPT_API_KEY"),
            os.getenv("WOW_TYPEGPT_API_KEY_2"),
            os.getenv("WOW_TYPEGPT_API_KEY_3"),
        ],
        "endpoint": "https://wow.typegpt.net/v1/chat/completions",
        "model_endpoint": "https://wow.typegpt.net/v1/models",
        "model_endpoint_auth": True,
        "model": "gpt-5",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": None,
        "temperature": None,
        "timeout": 60,
        "retries": 5,
        "backoff": 25,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 35,
        "daily_limit": 700,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "cerebras": {
        "id": 7,
        "priority": 10,
        "api_keys": [
            os.getenv("CEREBRAS_API_KEY"),
            os.getenv("CEREBRAS_API_KEY_2"),
            os.getenv("CEREBRAS_API_KEY_3"),
        ],
        "endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "model_endpoint": "https://api.cerebras.ai/v1/models",
        "model_endpoint_auth": True,
        "model": "gpt-oss-120b",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 4,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 60,
        "daily_limit": 2000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "cr": {
        "id": 23,
        "priority": 5,
        "api_keys": [
            os.getenv("CR_API_KEY"),
            os.getenv("CR_API_KEY_2"),
            os.getenv("CR_API_KEY_3"),
        ],
        "endpoint": "https://api.closerouter.com/v1/chat/completions",
        "model_endpoint": "https://api.closerouter.com/v1/models",
        "model_endpoint_auth": True,
        "model": "provider-6/gpt-4.1-mini",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": None,
        "temperature": None,
        "timeout": 60,
        "retries": 5,
        "backoff": 25,
        "format": "openai",
        "enabled": True,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "a3z": {
        "id": 8,
        "priority": 7,
        "api_keys": [None],  # No auth required
        "endpoint": "https://api.a3z.workers.dev/",
        "model_endpoint": "https://api.a3z.workers.dev/model",  # A3Z uses GET endpoint, no separate models endpoint
        "model_endpoint_auth": False,
        "model": "gpt-4.1-nano",
        "method": "GET",
        "auth_type": None,
        "max_tokens": None,
        "temperature": None,
        "timeout": 60,
        "retries": 3,
        "backoff": 1,
        "format": "a3z_get",
        "enabled": True,
        "rpm_limit": 30,
        "daily_limit": 500,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "gemini": {
        "id": 9,
        "priority": 3,
        "api_keys": [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI_API_KEY_3"),
        ],
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        "model_endpoint": None,  # Gemini doesn't have standard models endpoint
        "model_endpoint_auth": False,
        "model": "gemini-2.5-flash",
        "method": "POST",
        "auth_type": "query_param",  # Uses ?key= parameter
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 4,
        "backoff": 5,
        "format": "gemini",
        "enabled": True,
        "rpm_limit": 60,
        "daily_limit": 1500,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "openai": {
        "id": 10,
        "priority": 11,
        "api_keys": [
            os.getenv("OPENAI_API_KEY"),
            os.getenv("OPENAI_API_KEY_2"),
            os.getenv("OPENAI_API_KEY_3"),
        ],
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "model_endpoint": "https://api.openai.com/v1/models",
        "model_endpoint_auth": True,
        "model": "gpt-4-turbo-preview",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 4,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 500,
        "daily_limit": 10000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "groq": {
        "id": 11,
        "priority": 9,
        "api_keys": [
            os.getenv("GROQ_API_KEY"),
            os.getenv("GROQ_API_KEY_2"),
            os.getenv("GROQ_API_KEY_3"),
        ],
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "model_endpoint": "https://api.groq.com/openai/v1/models",
        "model_endpoint_auth": True,
        "model": "openai/gpt-oss-20b",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 4,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 30,
        "daily_limit": 1000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "omegatron": {
        "id": 12,
        "priority": 7,
        "api_keys": [None],  # No auth required
        "endpoint": "https://omegatron.onrender.com/v1/chat/completions",
        "model_endpoint": "https://omegatron.onrender.com/v1/models",
        "model_endpoint_auth": False,
        "model": "gpt-4.1-mini",
        "method": "POST",
        "auth_type": None,
        "max_tokens": None,
        "temperature": None,
        "timeout": 60,
        "retries": 3,
        "backoff": 1,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 25,
        "daily_limit": 400,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "offline": {
        "id": 13,
        "priority": 7,
        "api_keys": [None],
        "endpoint": "http://localhost:11434/api/generate",
        "model_endpoint": "http://localhost:11434/api/tags",  # Ollama has /tags endpoint
        "model_endpoint_auth": False,
        "model": "llama2",
        "method": "POST",
        "auth_type": None,
        "max_tokens": None,
        "temperature": None,
        "timeout": 60,
        "retries": 3,
        "backoff": 2,
        "format": "ollama",
        "enabled": False,  # Disabled by default (local server)
        "rpm_limit": 100,
        "daily_limit": 1000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "cloudflare": {
        "id": 14,
        "priority": 12,
        "api_keys": [
            os.getenv("CLOUDFLARE_API_KEY"),
            os.getenv("CLOUDFLARE_API_KEY_2"),
            os.getenv("CLOUDFLARE_API_KEY_3"),
        ],
        "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        "endpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions",
        "model_endpoint": None,  # Cloudflare doesn't have standard models endpoint
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
        "enabled": True,
        "rpm_limit": 100,
        "daily_limit": 2000,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "cohere": {
        "id": 15,
        "priority": 13,
        "api_keys": [
            os.getenv("COHERE_API_KEY"),
            os.getenv("COHERE_API_KEY_2"),
            os.getenv("COHERE_API_KEY_3"),
        ],
        "endpoint": "https://api.cohere.com/v2/chat",
        "model_endpoint": "https://api.cohere.com/v2/models",  # Cohere doesn't have standard models endpoint
        "model_endpoint_auth": False,
        "model": "command-a-03-2025",
        "method": "POST",
        "auth_type": "bearer_lowercase",
        "max_tokens": 4000,
        "temperature": 0.3,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "cohere",
        "enabled": True,
        "rpm_limit": 20,
        "daily_limit": 300,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "openrouter": {
        "id": 16,
        "priority": 14,
        "api_keys": [
            os.getenv("OPENROUTER_API_KEY"),
            os.getenv("OPENROUTER_API_KEY_2"),
            os.getenv("OPENROUTER_API_KEY_3"),
        ],
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "model_endpoint": "https://openrouter.ai/api/v1/models",
        "model_endpoint_auth": True,
        "model": "meta-llama/llama-3.1-405b-instruct:free",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 25,
        "daily_limit": 400,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "nvidia": {
        "id": 17,
        "priority": 15,
        "api_keys": [
            os.getenv("NVIDIA_API_KEY"),
            os.getenv("NVIDIA_API_KEY_2"),
            os.getenv("NVIDIA_API_KEY_3"),
        ],
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model_endpoint": "https://integrate.api.nvidia.com/v1/models",
        "model_endpoint_auth": True,
        "model": "deepseek-ai/deepseek-v3.1",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 512,
        "temperature": 1.0,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 30,
        "daily_limit": 500,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "vercel": {
        "id": 18,
        "priority": 16,
        "api_keys": [
            os.getenv("VERCEL_API_KEY"),
            os.getenv("VERCEL_API_KEY_2"),
            os.getenv("VERCEL_API_KEY_3"),
        ],
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
        "enabled": True,
        "rpm_limit": 15,
        "daily_limit": 150,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "github": {
        "id": 19,
        "priority": 17,
        "api_keys": [
            os.getenv("GITHUB_API_KEY"),
            os.getenv("GITHUB_API_KEY_2"),
            os.getenv("GITHUB_API_KEY_3"),
        ],
        "endpoint": "https://models.github.ai/inference/chat/completions",
        "model_endpoint": "https://models.github.ai/inference/models",
        "model_endpoint_auth": True,
        "model": "openai/gpt-4o",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": True,
        "rpm_limit": 15,
        "daily_limit": 150,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "flowith": {
        "id": 20,
        "priority": 18,
        "api_keys": [
            os.getenv("FLOWITH_API_KEY"),
            os.getenv("FLOWITH_API_KEY_2"),
            os.getenv("FLOWITH_API_KEY_3"),
        ],
        "endpoint": "https://edge.flowith.net/external/use/seek-knowledge",
        "model_endpoint": None,  # Flowith doesn't have standard models endpoint
        "model_endpoint_auth": False,
        "model": "gpt-4o-mini",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 2048,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "flowith",
        "enabled": True,
        "rpm_limit": 10,
        "daily_limit": 100,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "minimax": {
        "id": 21,
        "priority": 19,
        "api_keys": [
            os.getenv("MINIMAX_API_KEY"),
            os.getenv("MINIMAX_API_KEY_2"),
            os.getenv("MINIMAX_API_KEY_3"),
        ],
        "endpoint": "https://api.minimaxi.chat/v1/text/chatcompletion_v2",
        "model_endpoint": None,  # Minimax doesn't have standard models endpoint
        "model_endpoint_auth": False,
        "model": "minimax-reasoning-01",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 40000,
        "temperature": 1.0,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "minimax",
        "enabled": True,
        "rpm_limit": 5,
        "daily_limit": 50,
        "current_key_index": 0,
        "consecutive_failures": 0
    },
    "pawan": {
        "id": 22,
        "priority": 20,
        "api_keys": [
            os.getenv("PAWAN_API_KEY"),
            os.getenv("PAWAN_API_KEY_2"),
            os.getenv("PAWAN_API_KEY_3"),
        ],
        "endpoint": "https://api.pawan.krd/cosmosrp/v1/chat/completions",
        "model_endpoint": "https://api.pawan.krd/cosmosrp/v1/models",
        "model_endpoint_auth": True,
        "model": "gpt-4o-mini",
        "method": "POST",
        "auth_type": "bearer",
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": 60,
        "retries": 3,
        "backoff": 5,
        "format": "openai",
        "enabled": False,  # Disabled - poor quality provider
        "rpm_limit": 60,
        "daily_limit": 1000,
        "current_key_index": 0,
        "consecutive_failures": 0
    }
}

# Global Engine Settings
ENGINE_SETTINGS = {
    "default_timeout": 60,
    "max_retries": 3,
    "enable_auto_rotation": True,
    "consecutive_failure_limit": 5,  # Flag provider after 5 consecutive failures
    "key_rotation_enabled": True,    # Enable automatic key rotation
    "provider_rotation_enabled": True,  # Enable provider rotation on failure
    "verbose_mode": False,  # Global verbose mode for debugging/logging
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
    "enabled": True,  # Default enabled
    "cache_duration": 1800,  # 30 minutes in seconds
    "model_cache": {}  # Will store: {"gpt-4.1": [("openai", "gpt-4"), ("a4f", "provider-1/gpt-4.1")], ...}
}

# Verbose printing utility function
def verbose_print(message: str, verbose_override: bool = None):
    """
    Print message only if verbose mode is enabled
    
    Args:
        message (str): Message to print
        verbose_override (bool): Override global verbose setting
    """
    # Check verbose override first, then global setting
    if verbose_override is not None:
        is_verbose = verbose_override
    else:
        is_verbose = ENGINE_SETTINGS.get("verbose_mode", False)
    
    if is_verbose:
        try:
            print(message)
        except UnicodeEncodeError:
            # Fallback: replace problematic Unicode characters
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            print(safe_message)