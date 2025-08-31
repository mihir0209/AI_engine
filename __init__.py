"""
AI Engine V3.0 - Enterprise-Grade AI Provider Management System

This package provides a comprehensive solution for managing multiple AI providers
with advanced features like robust API key rotation, intelligent error detection,
automatic provider failover, and real-time server response analysis.

Key Features:
- 22 AI providers with automatic priority-based rotation
- Multi-key support with intelligent rotation (up to 3 keys per provider)
- Real-time error classification from server responses
- Automatic provider flagging and recovery
- Zero manual intervention required
- Comprehensive logging and monitoring
- Command-line testing interface

Components:
- ai_engine: Main AI Engine v3.0 with robust rotation and error handling
- config: External secure configuration with environment variables

Usage:
    from AI_engine import AI_engine
    
    # Initialize with verbose output
    engine = AI_engine(verbose=True)
    
    # Make a request with automatic provider rotation
    messages = [{"role": "user", "content": "Hello!"}]
    result = engine.chat_completion(messages)
    
    if result.success:
        print(f"Response: {result.content}")
        print(f"Provider used: {result.provider_used}")
    else:
        print(f"Error: {result.error_message}")

Command Line Usage:
    python -m AI_engine.ai_engine auto "Your message"      # Auto provider rotation
    python -m AI_engine.ai_engine cerebras "Your message"  # Specific provider
    python -m AI_engine.ai_engine list                     # List all providers
    python -m AI_engine.ai_engine status                   # Show engine status
    python -m AI_engine.ai_engine stress                   # Run stress test
"""

__version__ = "3.0.0"
__author__ = "SEO Automation Team"

# Import main components for easy access
try:
    from .ai_engine import AI_engine as AIEngine
    from .config import AI_CONFIGS, ENGINE_SETTINGS
    
    def get_ai_engine(verbose=True):
        """
        Factory function to get a configured AI Engine v3.0 instance
        
        Args:
            verbose (bool): Enable verbose logging output
            
        Returns:
            AI_engine: Configured AI Engine instance with all 22 providers
        """
        return AIEngine(verbose=verbose)
    
    def get_available_providers():
        """
        Get list of all configured providers
        
        Returns:
            dict: Dictionary of provider configurations
        """
        return AI_CONFIGS
    
    def get_engine_settings():
        """
        Get current engine settings
        
        Returns:
            dict: Engine configuration settings
        """
        return ENGINE_SETTINGS
    
    __all__ = [
        'AIEngine',
        'get_ai_engine',
        'get_available_providers', 
        'get_engine_settings',
        'AI_CONFIGS',
        'ENGINE_SETTINGS'
    ]
    
except ImportError as e:
    print(f"Warning: AI Engine v3.0 components could not be imported: {e}")
    __all__ = []
