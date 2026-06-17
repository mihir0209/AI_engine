"""
Base provider class for AI Engine
Provides abstract interface for provider implementations
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Generator
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProviderResponse:
    """Standardized response from any provider"""
    success: bool
    content: str = ""
    status_code: int = 0
    response_time: float = 0.0
    error_message: str = ""
    error_type: str = "unknown"
    provider_used: str = ""
    model_used: str = ""
    raw_response: Optional[Dict] = None
    streaming: bool = False


class BaseProvider(ABC):
    """Abstract base class for AI providers"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.priority = config.get('priority', 999)
        self.api_keys = config.get('api_keys', [])
        self.current_key_index = 0
    
    @abstractmethod
    def chat_completion(self, messages: List[Dict], model: str = None, **kwargs) -> ProviderResponse:
        """Send chat completion request"""
        pass
    
    @abstractmethod
    def chat_completion_stream(self, messages: List[Dict], model: str = None, **kwargs) -> Generator[Dict, None, None]:
        """Stream chat completion response"""
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models from this provider"""
        pass
    
    def get_current_api_key(self) -> Optional[str]:
        """Get current API key"""
        valid_keys = [k for k in self.api_keys if k]
        if not valid_keys:
            return None
        return valid_keys[self.current_key_index % len(valid_keys)]
    
    def rotate_api_key(self) -> Optional[str]:
        """Rotate to next API key"""
        valid_keys = [k for k in self.api_keys if k]
        if len(valid_keys) <= 1:
            return self.get_current_api_key()
        self.current_key_index = (self.current_key_index + 1) % len(valid_keys)
        return self.get_current_api_key()
    
    def health_check(self) -> Dict[str, Any]:
        """Check provider health status"""
        return {
            "provider": self.name,
            "enabled": self.enabled,
            "has_keys": bool([k for k in self.api_keys if k]),
            "priority": self.priority
        }
