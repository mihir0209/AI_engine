"""
Provider capabilities detection and management
Detects what features each provider supports
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ProviderCapabilities:
    """Capabilities of a provider"""
    provider: str
    vision: bool = False
    tool_calling: bool = False
    streaming: bool = False
    embeddings: bool = False
    function_calling: bool = False
    max_context_length: int = 4096
    supported_formats: List[str] = field(default_factory=lambda: ["text"])
    cost_tier: str = "medium"  # low, medium, high
    speed_tier: str = "medium"  # slow, medium, fast


# Pre-configured capabilities for known providers
PROVIDER_CAPABILITIES: Dict[str, ProviderCapabilities] = {
    "openai": ProviderCapabilities(
        provider="openai",
        vision=True,
        tool_calling=True,
        streaming=True,
        embeddings=True,
        function_calling=True,
        max_context_length=128000,
        supported_formats=["text", "image", "audio"],
        cost_tier="high",
        speed_tier="fast"
    ),
    "anthropic": ProviderCapabilities(
        provider="anthropic",
        vision=True,
        tool_calling=True,
        streaming=True,
        embeddings=False,
        function_calling=True,
        max_context_length=200000,
        supported_formats=["text", "image"],
        cost_tier="high",
        speed_tier="medium"
    ),
    "gemini": ProviderCapabilities(
        provider="gemini",
        vision=True,
        tool_calling=True,
        streaming=True,
        embeddings=True,
        function_calling=True,
        max_context_length=1000000,
        supported_formats=["text", "image", "video", "audio"],
        cost_tier="medium",
        speed_tier="fast"
    ),
    "groq": ProviderCapabilities(
        provider="groq",
        vision=False,
        tool_calling=True,
        streaming=True,
        embeddings=False,
        function_calling=True,
        max_context_length=32000,
        supported_formats=["text"],
        cost_tier="low",
        speed_tier="fast"
    ),
    "cloudflare": ProviderCapabilities(
        provider="cloudflare",
        vision=False,
        tool_calling=False,
        streaming=True,
        embeddings=True,
        function_calling=False,
        max_context_length=8192,
        supported_formats=["text"],
        cost_tier="low",
        speed_tier="fast"
    ),
}


class CapabilityManager:
    """Manages provider capabilities"""
    
    def __init__(self):
        self.capabilities: Dict[str, ProviderCapabilities] = dict(PROVIDER_CAPABILITIES)
        self.custom_capabilities: Dict[str, ProviderCapabilities] = {}
    
    def get_capabilities(self, provider: str) -> Optional[ProviderCapabilities]:
        """Get capabilities for a provider"""
        return self.custom_capabilities.get(provider) or self.capabilities.get(provider)
    
    def set_capabilities(self, provider: str, capabilities: ProviderCapabilities):
        """Set custom capabilities for a provider"""
        self.custom_capabilities[provider] = capabilities
    
    def supports_vision(self, provider: str) -> bool:
        """Check if provider supports vision"""
        caps = self.get_capabilities(provider)
        return caps.vision if caps else False
    
    def supports_tool_calling(self, provider: str) -> bool:
        """Check if provider supports tool calling"""
        caps = self.get_capabilities(provider)
        return caps.tool_calling if caps else False
    
    def supports_streaming(self, provider: str) -> bool:
        """Check if provider supports streaming"""
        caps = self.get_capabilities(provider)
        return caps.streaming if caps else False
    
    def get_providers_with_vision(self) -> List[str]:
        """Get all providers that support vision"""
        return [name for name, caps in self.capabilities.items() if caps.vision]
    
    def get_providers_with_tool_calling(self) -> List[str]:
        """Get all providers that support tool calling"""
        return [name for name, caps in self.capabilities.items() if caps.tool_calling]
    
    def get_fastest_providers(self, top_n: int = 3) -> List[str]:
        """Get fastest providers"""
        speed_order = {"fast": 0, "medium": 1, "slow": 2}
        sorted_providers = sorted(
            self.capabilities.items(),
            key=lambda x: speed_order.get(x[1].speed_tier, 1)
        )
        return [name for name, _ in sorted_providers[:top_n]]
    
    def get_cheapest_providers(self, top_n: int = 3) -> List[str]:
        """Get cheapest providers"""
        cost_order = {"low": 0, "medium": 1, "high": 2}
        sorted_providers = sorted(
            self.capabilities.items(),
            key=lambda x: cost_order.get(x[1].cost_tier, 1)
        )
        return [name for name, _ in sorted_providers[:top_n]]
    
    def get_provider_for_task(self, task_type: str) -> List[str]:
        """Get best providers for a task type"""
        recommendations = {
            "vision": self.get_providers_with_vision(),
            "tool_calling": self.get_providers_with_tool_calling(),
            "fast": self.get_fastest_providers(),
            "cheap": self.get_cheapest_providers(),
        }
        return recommendations.get(task_type, list(self.capabilities.keys()))
    
    def get_all_capabilities(self) -> Dict[str, Dict]:
        """Get all provider capabilities"""
        return {
            name: {
                "vision": caps.vision,
                "tool_calling": caps.tool_calling,
                "streaming": caps.streaming,
                "embeddings": caps.embeddings,
                "max_context_length": caps.max_context_length,
                "cost_tier": caps.cost_tier,
                "speed_tier": caps.speed_tier
            }
            for name, caps in self.capabilities.items()
        }


class ErrorMessageManager:
    """Manages user-friendly error messages"""
    
    ERROR_MESSAGES = {
        "rate_limit": {
            "message": "Rate limit exceeded. Please wait before retrying.",
            "suggestion": "Try a different provider or wait a few minutes.",
            "code": "RATE_LIMIT_EXCEEDED"
        },
        "auth_error": {
            "message": "Authentication failed. Invalid or missing API key.",
            "suggestion": "Check your API key configuration in .env file.",
            "code": "AUTH_FAILED"
        },
        "quota_exceeded": {
            "message": "Daily quota exceeded for this provider.",
            "suggestion": "Try a different provider or wait until quota resets.",
            "code": "QUOTA_EXCEEDED"
        },
        "service_unavailable": {
            "message": "Provider service is currently unavailable.",
            "suggestion": "Try again later or use a different provider.",
            "code": "SERVICE_UNAVAILABLE"
        },
        "timeout": {
            "message": "Request timed out.",
            "suggestion": "Try a shorter prompt or use a faster provider.",
            "code": "TIMEOUT"
        },
        "empty_response": {
            "message": "Provider returned an empty response.",
            "suggestion": "Try rephrasing your message.",
            "code": "EMPTY_RESPONSE"
        },
        "model_not_found": {
            "message": "Requested model not found.",
            "suggestion": "Check available models with GET /v1/models.",
            "code": "MODEL_NOT_FOUND"
        },
        "no_providers": {
            "message": "No providers available.",
            "suggestion": "Configure at least one provider in config.py.",
            "code": "NO_PROVIDERS"
        },
        "provider_not_found": {
            "message": "Provider not found.",
            "suggestion": "Check available providers with GET /api/providers.",
            "code": "PROVIDER_NOT_FOUND"
        },
        "chat_not_found": {
            "message": "Chat not found.",
            "suggestion": "Check the chat ID or create a new chat.",
            "code": "CHAT_NOT_FOUND"
        },
        "message_not_found": {
            "message": "Message not found.",
            "suggestion": "Check the message ID.",
            "code": "MESSAGE_NOT_FOUND"
        },
        "file_too_large": {
            "message": "File exceeds maximum size limit (10MB).",
            "suggestion": "Compress or split the file.",
            "code": "FILE_TOO_LARGE"
        },
        "invalid_file_type": {
            "message": "File type not supported.",
            "suggestion": "Use supported formats: .txt, .md, .json, .py, .js, .ts, .html, .css, .yaml, .png, .jpg",
            "code": "INVALID_FILE_TYPE"
        },
        "circuit_open": {
            "message": "Service temporarily unavailable due to repeated failures.",
            "suggestion": "Wait a moment and try again.",
            "code": "CIRCUIT_OPEN"
        }
    }
    
    @classmethod
    def get_error(cls, error_type: str, details: str = None) -> Dict:
        """Get formatted error message"""
        error_info = cls.ERROR_MESSAGES.get(error_type, {
            "message": f"Unknown error: {error_type}",
            "suggestion": "Please try again or contact support.",
            "code": "UNKNOWN_ERROR"
        })
        
        result = dict(error_info)
        if details:
            result["details"] = details
        
        return result
    
    @classmethod
    def get_all_errors(cls) -> Dict:
        """Get all error messages"""
        return cls.ERROR_MESSAGES


# Global instances
capability_manager = CapabilityManager()
error_message_manager = ErrorMessageManager()
