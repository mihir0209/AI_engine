"""
Provider and model capabilities detection and management.
Tracks vision, tool calling, streaming, etc. at BOTH provider and model level.
Loads pre-computed cache from data/capabilities_cache.json for fast startup.
"""
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ModelCapabilities:
    """Capabilities of a specific model"""
    vision: bool = False
    tool_calling: bool = False
    streaming: bool = True
    embeddings: bool = False
    max_context_length: int = 4096
    supported_formats: List[str] = field(default_factory=lambda: ["text"])


@dataclass
class ProviderCapabilities:
    """Capabilities of a provider (fallback when model-level unknown)"""
    provider: str
    vision: bool = False
    tool_calling: bool = False
    streaming: bool = True
    embeddings: bool = False
    max_context_length: int = 4096
    supported_formats: List[str] = field(default_factory=lambda: ["text"])


# ============================================
# MODEL-LEVEL CAPABILITY DATABASE
# ============================================
# Only models that actually support vision are marked vision=True
# If a model is not listed, it's treated as text-only (conservative)

MODEL_CAPABILITIES: Dict[str, Dict[str, ModelCapabilities]] = {
    "gemini": {
        "gemini-2.5-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-2.5-flash-lite": ModelCapabilities(vision=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-2.0-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-2.0-flash-lite": ModelCapabilities(vision=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-1.5-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-1.5-pro": ModelCapabilities(vision=True, tool_calling=True, max_context_length=2000000, supported_formats=["text", "image"]),
    },
    "groq": {
        "llama-3.3-70b-versatile": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "llama-3.1-8b-instant": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "mixtral-8x7b-32768": ModelCapabilities(max_context_length=32768),
        "gemma2-9b-it": ModelCapabilities(max_context_length=8192),
        "meta-llama/llama-4-scout-17b-16e-instruct": ModelCapabilities(tool_calling=True, max_context_length=131072),
    },
    "nvidia": {
        "nvidia/nemotron-3-nano-30b-a3b": ModelCapabilities(tool_calling=True, max_context_length=4096),
        "meta/llama-3.1-8b-instruct": ModelCapabilities(max_context_length=4096),
        "mistralai/mistral-7b-instruct-v0.3": ModelCapabilities(max_context_length=4096),
    },
    "openrouter": {
        "google/gemini-2.5-flash-preview": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000),
        "meta-llama/llama-4-maverick-17b-128e-instruct": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000),
        "openai/gpt-4o-mini": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000),
    },
    "cloudflare": {
        "meta/llama-3.1-8b-instruct-fp8": ModelCapabilities(max_context_length=8192),
        "meta/llama-3-8b-instruct": ModelCapabilities(max_context_length=8192),
    },
    "cerebras": {
        "llama-3.3-70b": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "llama-3.1-8b": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "zai-glm-4.7": ModelCapabilities(max_context_length=128000),
        "gpt-oss-120b": ModelCapabilities(max_context_length=128000),
    },
    "cohere": {
        "command-r-plus": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "command-r": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "command": ModelCapabilities(max_context_length=4096),
    },
    "mistral": {
        "mistral-large-latest": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "mistral-small-latest": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "pixtral-large-latest": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000),
    },
    "kilo": {
        "kilo-auto/free": ModelCapabilities(max_context_length=128000),
        "nvidia/nemotron-ultra-253b-vl": ModelCapabilities(vision=True, max_context_length=131072),
        "google/gemma-4-27b-it-bf16": ModelCapabilities(max_context_length=128000),
    },
    "zai": {
        "glm-4.7-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
        "glm-4.5-flash": ModelCapabilities(vision=True, max_context_length=128000, supported_formats=["text", "image"]),
        "glm-4.6v-flash": ModelCapabilities(vision=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
}

# ============================================
# PROVIDER-LEVEL FALLBACKS
# ============================================
PROVIDER_CAPABILITIES: Dict[str, ProviderCapabilities] = {
    "gemini": ProviderCapabilities(provider="gemini", vision=True, tool_calling=True, max_context_length=1000000, supported_formats=["text", "image"]),
    "groq": ProviderCapabilities(provider="groq", vision=False, tool_calling=True, max_context_length=128000, supported_formats=["text"]),
    "nvidia": ProviderCapabilities(provider="nvidia", vision=False, tool_calling=True, max_context_length=4096, supported_formats=["text"]),
    "openrouter": ProviderCapabilities(provider="openrouter", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "cloudflare": ProviderCapabilities(provider="cloudflare", vision=False, max_context_length=8192, supported_formats=["text"]),
    "cerebras": ProviderCapabilities(provider="cerebras", vision=False, tool_calling=True, max_context_length=128000, supported_formats=["text"]),
    "cohere": ProviderCapabilities(provider="cohere", vision=False, tool_calling=True, max_context_length=128000, supported_formats=["text"]),
    "mistral": ProviderCapabilities(provider="mistral", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "huggingface": ProviderCapabilities(provider="huggingface", vision=False, max_context_length=4096, supported_formats=["text"]),
    "kilo": ProviderCapabilities(provider="kilo", vision=True, max_context_length=128000, supported_formats=["text", "image"]),
    "github": ProviderCapabilities(provider="github", vision=True, max_context_length=128000, supported_formats=["text", "image"]),
    "vercel": ProviderCapabilities(provider="vercel", vision=False, max_context_length=4096, supported_formats=["text"]),
    "opencode_zen": ProviderCapabilities(provider="opencode_zen", vision=False, max_context_length=4096, supported_formats=["text"]),
    "pollinations": ProviderCapabilities(provider="pollinations", vision=False, max_context_length=4096, supported_formats=["text"]),
    "hermes": ProviderCapabilities(provider="hermes", vision=False, max_context_length=4096, supported_formats=["text"]),
    "longcat": ProviderCapabilities(provider="longcat", vision=False, max_context_length=4096, supported_formats=["text"]),
    "zai": ProviderCapabilities(provider="zai", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "hcnsec": ProviderCapabilities(provider="hcnsec", vision=True, max_context_length=128000, supported_formats=["text", "image"]),
    "mimo": ProviderCapabilities(provider="mimo", vision=False, max_context_length=4096, supported_formats=["text"]),
    "paxsenix": ProviderCapabilities(provider="paxsenix", vision=False, max_context_length=4096, supported_formats=["text"]),
    "llm7": ProviderCapabilities(provider="llm7", vision=False, max_context_length=4096, supported_formats=["text"]),
    "g4f_groq": ProviderCapabilities(provider="g4f_groq", vision=False, max_context_length=128000, supported_formats=["text"]),
    "g4f_gemini": ProviderCapabilities(provider="g4f_gemini", vision=True, max_context_length=1000000, supported_formats=["text", "image"]),
    "g4f_ollama": ProviderCapabilities(provider="g4f_ollama", vision=False, max_context_length=4096, supported_formats=["text"]),
    "g4f_pollinations": ProviderCapabilities(provider="g4f_pollinations", vision=False, max_context_length=4096, supported_formats=["text"]),
    "g4f_nvidia": ProviderCapabilities(provider="g4f_nvidia", vision=False, max_context_length=4096, supported_formats=["text"]),
}


class CapabilityManager:
    """Manages provider and model capabilities with vision detection"""

    def __init__(self):
        self.model_caps: Dict[str, Dict[str, ModelCapabilities]] = dict(MODEL_CAPABILITIES)
        self.provider_caps: Dict[str, ProviderCapabilities] = dict(PROVIDER_CAPABILITIES)
        self.custom_caps: Dict[str, ProviderCapabilities] = {}
        self._cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load pre-computed capabilities cache"""
        cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'capabilities_cache.json')
        if os.path.exists(cache_path):
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _rebuild_cache(self):
        """Rebuild and save the capabilities cache"""
        cache = {
            'vision_providers': self.get_vision_providers(),
            'provider_capabilities': {},
            'model_capabilities': {},
            'image_compatibility': {},
        }
        for name, caps in self.provider_caps.items():
            cache['provider_capabilities'][name] = {
                'vision': caps.vision, 'tool_calling': caps.tool_calling,
                'streaming': caps.streaming, 'max_context_length': caps.max_context_length,
                'supported_formats': caps.supported_formats,
            }
        for provider, models in self.model_caps.items():
            for model_name, caps in models.items():
                cache['model_capabilities'][f'{provider}/{model_name}'] = {
                    'vision': caps.vision, 'tool_calling': caps.tool_calling,
                    'streaming': caps.streaming, 'max_context_length': caps.max_context_length,
                    'supported_formats': caps.supported_formats,
                }
        cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'capabilities_cache.json')
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(cache, f, indent=2)
        self._cache = cache

    def get_model_capabilities(self, provider: str, model: str) -> Optional[ModelCapabilities]:
        """Get capabilities for a specific model under a provider"""
        provider_models = self.model_caps.get(provider, {})
        if model in provider_models:
            return provider_models[model]
        for pattern, caps in provider_models.items():
            if model and pattern in model:
                return caps
        return None

    def get_provider_capabilities(self, provider: str) -> Optional[ProviderCapabilities]:
        """Get provider-level capabilities (fallback)"""
        return self.custom_caps.get(provider) or self.provider_caps.get(provider)

    def supports_vision(self, provider: str, model: str = None) -> bool:
        """Check if a provider/model supports vision/image input.
        
        Uses fuzzy matching on model name: looks for vision-related keywords
        like 'vl', 'vision', 'vlm', 'multimodal', etc.
        """
        if model:
            # 1. Check exact model database
            model_caps = self.get_model_capabilities(provider, model)
            if model_caps:
                return model_caps.vision

            # 2. Fuzzy match on model name keywords
            vision_keywords = [
                "vl", "vision", "vlm", "multimodal", "image", "visual",
                "clip", "img", "pixtral", "fuyu",
            ]
            model_lower = model.lower()
            for kw in vision_keywords:
                if kw in model_lower:
                    return True

        provider_caps = self.get_provider_capabilities(provider)
        return provider_caps.vision if provider_caps else False

    def supports_tool_calling(self, provider: str, model: str = None) -> bool:
        if model:
            model_caps = self.get_model_capabilities(provider, model)
            if model_caps:
                return model_caps.tool_calling
        provider_caps = self.get_provider_capabilities(provider)
        return provider_caps.tool_calling if provider_caps else False

    def get_max_context(self, provider: str, model: str = None) -> int:
        if model:
            model_caps = self.get_model_capabilities(provider, model)
            if model_caps:
                return model_caps.max_context_length
        provider_caps = self.get_provider_capabilities(provider)
        return provider_caps.max_context_length if provider_caps else 4096

    def get_vision_providers(self) -> List[str]:
        """Get all providers that support vision at provider level"""
        return [name for name, caps in self.provider_caps.items() if caps.vision]

    def get_all_capabilities(self) -> Dict[str, Dict]:
        """Get all provider capabilities"""
        return {
            name: {
                "vision": caps.vision,
                "tool_calling": caps.tool_calling,
                "streaming": caps.streaming,
                "max_context_length": caps.max_context_length,
                "supported_formats": caps.supported_formats,
            }
            for name, caps in self.provider_caps.items()
        }

    def get_model_list(self) -> List[Dict]:
        """Get all known models with their capabilities"""
        result = []
        for provider, models in self.model_caps.items():
            for model_name, caps in models.items():
                result.append({
                    "provider": provider,
                    "model": model_name,
                    "vision": caps.vision,
                    "tool_calling": caps.tool_calling,
                    "max_context_length": caps.max_context_length,
                })
        return result

    def check_image_compatibility(self, provider: str, model: str = None) -> Dict:
        """Check if a provider/model can handle image uploads.
        When model is None/default, always return compatible — autodecide handles vision routing.
        Returns: {compatible: bool, reason: str, suggestions: list}
        """
        # If no specific model, always compatible (autodecide will route to vision provider)
        if not model or model in ("auto", "default", ""):
            return {"compatible": True, "reason": "Model is auto/default — autodecide will route to vision provider", "suggestions": []}

        vision_ok = self.supports_vision(provider, model)

        if vision_ok:
            return {"compatible": True, "reason": "Model supports vision", "suggestions": []}

        # Find vision providers with their best models
        suggestions = []
        for prov_name, prov_caps in self.provider_caps.items():
            if prov_caps.vision:
                best_model = None
                prov_models = self.model_caps.get(prov_name, {})
                for model_name, caps in prov_models.items():
                    if caps.vision:
                        best_model = model_name
                        break
                if best_model:
                    suggestions.append(f"{prov_name} ({best_model})")
                else:
                    suggestions.append(prov_name)

        return {
            "compatible": False,
            "reason": f"'{provider}' with model '{model}' does not support image input",
            "suggestions": suggestions[:5],
        }


class ErrorMessageManager:
    """Manages user-friendly error messages"""

    ERROR_MESSAGES = {
        "rate_limit": {"message": "Rate limit exceeded. Please wait before retrying.", "suggestion": "Try a different provider or wait a few minutes.", "code": "RATE_LIMIT_EXCEEDED"},
        "auth_error": {"message": "Authentication failed. Invalid or missing API key.", "suggestion": "Check your API key configuration in .env file.", "code": "AUTH_FAILED"},
        "quota_exceeded": {"message": "Daily quota exceeded for this provider.", "suggestion": "Try a different provider or wait until quota resets.", "code": "QUOTA_EXCEEDED"},
        "service_unavailable": {"message": "Provider service is currently unavailable.", "suggestion": "Try again later or use a different provider.", "code": "SERVICE_UNAVAILABLE"},
        "timeout": {"message": "Request timed out.", "suggestion": "Try a shorter prompt or use a faster provider.", "code": "TIMEOUT"},
        "empty_response": {"message": "Provider returned an empty response.", "suggestion": "Try rephrasing your message.", "code": "EMPTY_RESPONSE"},
        "model_not_found": {"message": "Requested model not found.", "suggestion": "Check available models with GET /v1/models.", "code": "MODEL_NOT_FOUND"},
        "no_providers": {"message": "No providers available.", "suggestion": "Configure at least one provider in config.py.", "code": "NO_PROVIDERS"},
        "no_vision_support": {"message": "This model does not support image input.", "suggestion": "Switch to a vision-capable provider (Gemini, OpenRouter, Mistral).", "code": "NO_VISION_SUPPORT"},
        "provider_not_found": {"message": "Provider not found.", "suggestion": "Check available providers with GET /api/providers.", "code": "PROVIDER_NOT_FOUND"},
        "chat_not_found": {"message": "Chat not found.", "suggestion": "Check the chat ID or create a new chat.", "code": "CHAT_NOT_FOUND"},
        "message_not_found": {"message": "Message not found.", "suggestion": "Check the message ID.", "code": "MESSAGE_NOT_FOUND"},
        "file_too_large": {"message": "File exceeds maximum size limit (10MB).", "suggestion": "Compress or split the file.", "code": "FILE_TOO_LARGE"},
        "invalid_file_type": {"message": "File type not supported.", "suggestion": "Use supported formats: .txt, .md, .json, .py, .js, .ts, .html, .css, .yaml, .png, .jpg", "code": "INVALID_FILE_TYPE"},
        "circuit_open": {"message": "Service temporarily unavailable due to repeated failures.", "suggestion": "Wait a moment and try again.", "code": "CIRCUIT_OPEN"},
    }

    @classmethod
    def get_error(cls, error_type: str, details: str = None) -> Dict:
        error_info = cls.ERROR_MESSAGES.get(error_type, {"message": f"Unknown error: {error_type}", "suggestion": "Please try again or contact support.", "code": "UNKNOWN_ERROR"})
        result = dict(error_info)
        if details:
            result["details"] = details
        return result

    @classmethod
    def get_all_errors(cls) -> Dict:
        return cls.ERROR_MESSAGES


capability_manager = CapabilityManager()
error_message_manager = ErrorMessageManager()
