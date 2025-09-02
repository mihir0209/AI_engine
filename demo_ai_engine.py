#!/usr/bin/env python3
"""
AI Engine v3.0 - Quick Feature Demonstration

This file demonstrates the core features of AI Engine v3.0 in under 10 seconds.
Each section shows key functionality with minimal API calls for speed.

Author: AI Engine Team
Date: September 2025
License: MIT
"""

import os
import sys
import time
from typing import Dict, List, Any

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_engine import get_ai_engine, AI_engine
from config import AI_CONFIGS, ENGINE_SETTINGS, AUTODECIDE_CONFIG

def print_section(title: str, description: str = ""):
    """Print a formatted section header with timing info"""
    print("\n" + "=" * 80)
    print(f"🚀 {title}")
    if description:
        print(f"📝 {description}")
    print("=" * 80)

def print_info(message: str):
    """Print an informational message with consistent formatting"""
    print(f"📋 {message}")

def print_demo_step(step: str):
    """Print a demo step with clear formatting"""
    print(f"\n🔸 DEMO STEP: {step}")
    print("-" * 60)

def print_warning(message: str):
    """Print a warning message"""
    print(f"⚠️  {message}")

def print_success(message: str):
    """Print a success message"""
    print(f"✅ {message}")

def print_feature(message: str):
    """Print a feature highlight"""
    print(f"🎯 {message}")

def quick_basic_demo(verbose_mode: bool = False):
    """
    ============================================================================
    SECTION 1: BASIC ENGINE INITIALIZATION AND STATUS
    ============================================================================
    This section demonstrates:
    - Engine initialization with provider loading
    - Configuration display
    - Basic status information
    - Provider health overview
    """
    print_section("1. Basic Engine Initialization", "Loading providers and checking configuration")
    
    print_demo_step("Initializing AI Engine with 24 provider configurations...")
    start_time = time.time()
    
    # Initialize engine with verbose setting based on user choice
    engine = get_ai_engine(verbose=verbose_mode)
    init_time = time.time() - start_time
    
    print_info(f"Engine initialized in {init_time:.2f} seconds")
    print_info(f"Total configured providers: {len(AI_CONFIGS)} providers")
    print_info(f"Loaded active providers: {len(engine.providers)} providers")
    
    # Get status without heavy operations
    status = engine.get_status()
    print_info(f"Available providers: {status['available_providers']}")
    print_info(f"Flagged providers: {status['flagged_providers']}")
    
    # Show verbose-specific information
    if verbose_mode:
        print_demo_step("Verbose Mode - Engine Configuration Details:")
        print_info(f"Engine verbose mode: {engine.verbose}")
        print_info(f"Provider initialization details shown above")
        print_info(f"Detailed logging enabled for all operations")
    else:
        print_demo_step("Engine Configuration Overview:")
    
    print_info(f"Key rotation: {'Enabled' if ENGINE_SETTINGS.get('key_rotation_enabled', True) else 'Disabled'}")
    print_info(f"Failure limit: {ENGINE_SETTINGS.get('consecutive_failure_limit', 5)} failures")
    print_info(f"Autodecide feature: {'Enabled' if AUTODECIDE_CONFIG.get('enabled', True) else 'Disabled'}")
    
    return engine

def quick_provider_demo(engine: AI_engine):
    """
    ============================================================================
    SECTION 2: PROVIDER MANAGEMENT OVERVIEW
    ============================================================================
    This section demonstrates:
    - Provider categorization (enabled/disabled/no-auth)
    - Configuration overview without API calls
    - Key management status
    - Provider priority system
    """
    print_section("2. Provider Management System", "Provider categories and configuration")
    
    print_demo_step("Analyzing provider configurations...")
    
    # Categorize providers quickly without API calls
    enabled_providers = []
    disabled_providers = []
    no_auth_providers = []
    
    for name, config in AI_CONFIGS.items():
        if not config.get('enabled', True):
            disabled_providers.append(name)
        elif config.get('auth_type') is None:
            no_auth_providers.append(name)
        else:
            enabled_providers.append(name)
    
    print_info(f"Provider Categories:")
    print(f"    ✅ Enabled with API keys: {len(enabled_providers)} providers")
    print(f"       Examples: {', '.join(enabled_providers[:5])}")
    print(f"    🔓 No authentication needed: {len(no_auth_providers)} providers")
    print(f"       Examples: {', '.join(no_auth_providers)}")
    print(f"    ❌ Disabled/No keys: {len(disabled_providers)} providers")
    print(f"       Examples: {', '.join(disabled_providers)}")
    
    print_demo_step("Key Rotation Configuration:")
    providers_with_multiple_keys = 0
    # Check configuration of first 5 enabled providers for speed
    for provider_name in enabled_providers[:5]:  # Check only first 5 for speed
        config = AI_CONFIGS.get(provider_name, {})
        if config.get('api_keys') and len([k for k in config['api_keys'] if k]) > 1:
            providers_with_multiple_keys += 1
    
    print_info(f"Providers with backup keys configured: {providers_with_multiple_keys} (sample of 5)")
    print_info("Key rotation triggers: rate limits, auth errors, quota exceeded")

def quick_autodecide_demo(engine: AI_engine):
    """
    ============================================================================
    SECTION 3: AUTODECIDE FEATURE (SIMULATED)
    ============================================================================
    This section demonstrates:
    - Model name normalization
    - Provider discovery simulation (no actual API calls)
    - Intelligent provider selection
    - Cache optimization
    """
    print_section("3. Autodecide System", "Intelligent model-to-provider matching")
    
    print_demo_step("Model Name Normalization Examples:")
    test_models = [
        ("gpt-4", "Standard format"),
        ("GPT-4", "Uppercase variant"),
        ("gpt4", "Compact format"),
        ("claude-3", "Claude format"),
        ("llama-3.1", "Llama format")
    ]
    
    for model, description in test_models:
        normalized = engine.normalize_model_name(model)
        print(f"    {model:12} -> {normalized:12} ({description})")
    
    print_demo_step("Provider Discovery Simulation:")
    print_info("In real usage, autodecide discovers providers by:")
    print("    1. Querying each provider's /models endpoint")
    print("    2. Fuzzy matching requested model names")
    print("    3. Ranking by provider priority and performance")
    print("    4. Caching results for 60 minutes")
    
    # Simulate typical discovery results
    sample_results = {
        "gpt-4": ["paxsenix", "chi", "openai", "mango", "samurai"],
        "claude": ["paxsenix", "anthropic", "openrouter"],
        "llama": ["groq", "nvidia", "openrouter", "cerebras"]
    }
    
    for model, providers in sample_results.items():
        print_info(f"Model '{model}' typically found in {len(providers)} providers")
        print(f"       Top choices: {', '.join(providers[:3])}")

def quick_api_demo(engine: AI_engine, verbose_mode: bool = False):
    """
    ============================================================================
    SECTION 4: SINGLE API CALL DEMONSTRATION
    ============================================================================
    This section demonstrates:
    - Real chat completion with automatic provider selection
    - Response handling and timing
    - Provider selection process
    - Error handling (if applicable)
    """
    print_section("4. Live API Demonstration", "Single chat completion to show real functionality")
    
    print_demo_step("Making ONE real API call to demonstrate functionality...")
    print_info("This will use automatic provider selection based on priorities")
    
    if verbose_mode:
        print_info("🔊 Verbose mode: You will see detailed API call information")
    else:
        print_info("🔇 Quiet mode: Showing only essential API call results")
    
    # Prepare a simple, fast message
    messages = [{"role": "user", "content": "Respond with exactly: 'AI Engine demo successful'"}]
    
    start_time = time.time()
    result = engine.chat_completion(messages)
    call_time = time.time() - start_time
    
    if result.success:
        print_info(f"✅ API call successful in {call_time:.2f} seconds")
        print_info(f"Provider used: {result.provider_used}")
        print_info(f"Model used: {result.model_used}")
        print_info(f"Response: {result.content[:50]}...")
        
        if verbose_mode:
            print_demo_step("Verbose Mode - Additional API Details:")
            print_info(f"Full response content: {result.content}")
            print_info(f"Response time breakdown: {call_time:.3f} seconds")
            print_info(f"Provider priority used for selection")
            if hasattr(result, 'tokens_used'):
                print_info(f"Tokens used: {getattr(result, 'tokens_used', 'N/A')}")
        
        print_demo_step("This demonstrates:")
        print("    ✅ Automatic provider selection")
        print("    ✅ Real-time API key management")
        print("    ✅ Response parsing and timing")
        print("    ✅ Error handling and recovery")
    else:
        print_info(f"❌ API call failed: {result.error_message}")
        print_info(f"Error type: {result.error_type}")
        
        if verbose_mode:
            print_demo_step("Verbose Mode - Error Analysis:")
            print_info(f"Error classification: {result.error_type}")
            print_info(f"Provider attempted: {result.provider_used or 'Unknown'}")
            print_info("This would trigger automatic failover in normal usage")
        
        print_demo_step("This demonstrates:")
        print("    🔄 Automatic error detection")
        print("    🚨 Error classification system")
        print("    🔄 Provider flagging and rotation")

def quick_features_overview():
    """
    ============================================================================
    SECTION 5: FEATURE OVERVIEW (NO API CALLS)
    ============================================================================
    This section demonstrates:
    - Complete feature list
    - Architecture overview
    - Usage patterns
    - Advanced capabilities
    """
    print_section("5. Advanced Features Overview", "Complete system capabilities")
    
    print_demo_step("Core Features:")
    features = [
        "24 AI Provider Support (OpenAI, Gemini, Claude, Llama, etc.)",
        "Automatic Failover with intelligent provider selection",
        "Multi-key API key rotation (up to 3 keys per provider)",
        "8-type error classification with specific recovery actions",
        "Autodecide: automatic model-to-provider matching",
        "FastAPI web server with dashboard and REST APIs",
        "Real-time performance monitoring and statistics",
        "OpenAI-compatible endpoints for easy integration"
    ]
    
    for i, feature in enumerate(features, 1):
        print(f"    {i}. {feature}")
    
    print_demo_step("Error Handling System:")
    error_types = [
        ("rate_limit", "Key rotation + 1 hour flagging"),
        ("auth_error", "Key rotation + 1 hour flagging"),
        ("quota_exceeded", "Key rotation + 1 hour flagging"),
        ("service_unavailable", "Provider flagging + 10 minutes"),
        ("server_error", "Provider flagging + 10 minutes"),
        ("network_error", "Provider flagging + 10 minutes"),
        ("bad_request", "Immediate provider switch"),
        ("unknown", "30 minute flagging")
    ]
    
    for error_type, action in error_types:
        print(f"    {error_type:18} -> {action}")
    
    print_demo_step("Web Server Capabilities:")
    endpoints = [
        "/v1/chat/completions - OpenAI-compatible chat API",
        "/v1/models - List all available models",
        "/api/providers - Provider management and testing",
        "/api/autodecide/{model} - Model discovery API",
        "/ - Web dashboard with real-time monitoring"
    ]
    
    for endpoint in endpoints:
        print(f"    📡 {endpoint}")

def quick_usage_examples():
    """
    ============================================================================
    SECTION 6: PRACTICAL USAGE EXAMPLES
    ============================================================================
    This section demonstrates:
    - Code examples for common use cases
    - Integration patterns
    - CLI usage examples
    - Web server startup
    """
    print_section("6. Usage Examples", "Practical code examples for integration")
    
    print_demo_step("Python Integration Examples:")
    
    print("\n📋 Basic Usage:")
    print("""
    from ai_engine import get_ai_engine
    
    engine = get_ai_engine(verbose=True)
    messages = [{"role": "user", "content": "Hello!"}]
    result = engine.chat_completion(messages)
    
    if result.success:
        print(f"Response: {result.content}")
        print(f"Provider: {result.provider_used}")
    """)
    
    print("\n📋 Autodecide Usage:")
    print("""
    # Automatically find best provider for any model
    result = engine.chat_completion(
        messages=[{"role": "user", "content": "Hello!"}],
        model="gpt-4",  # Engine finds best provider
        autodecide=True
    )
    """)
    
    print("\n📋 Specific Provider Testing:")
    print("""
    # Test individual providers
    result = engine.test_specific_provider("groq", "Test message")
    
    # Get engine status
    status = engine.get_status()
    print(f"Available: {status['available_providers']}")
    """)
    
    print_demo_step("Command Line Usage:")
    cli_examples = [
        "# AI Engine Demo Commands:",
        "python demo_ai_engine.py              # Run demo in quiet mode",
        "python demo_ai_engine.py verbose      # Run demo with detailed logging",
        "python demo_ai_engine.py help         # Show demo help and options",
        "",
        "# Direct AI Engine Commands:",
        "python ai_engine.py auto 'Hello world'  # Auto provider selection",
        "python ai_engine.py autodecide gpt-4 'Hi' # Autodecide for specific model",
        "python ai_engine.py groq 'Test message' # Specific provider test",
        "python ai_engine.py status              # System status",
        "python ai_engine.py list                # List all providers", 
        "python ai_engine.py keys                # Key usage statistics",
        "python ai_engine.py stress              # Comprehensive stress test",
        "python server.py                        # Start web server"
    ]
    
    for example in cli_examples:
        if example.startswith('#'):
            print(f"\n📋 {example}")
        elif example == "":
            continue
        else:
            print(f"    $ {example}")

def print_demo_help():
    """Print help information for demo usage"""
    print_section("AI Engine Demo - Usage Help", "Command line options and examples")
    
    print_demo_step("Demo Usage Options:")
    print("📋 python demo_ai_engine.py           # Run demo in quiet mode (default)")
    print("📋 python demo_ai_engine.py verbose   # Run demo with detailed logging")
    print("📋 python demo_ai_engine.py quiet     # Run demo in quiet mode (explicit)")
    print("📋 python demo_ai_engine.py help      # Show this help message")
    
    print_demo_step("Alternative Commands:")
    print("📋 python demo_ai_engine.py -v        # Verbose mode (short)")
    print("📋 python demo_ai_engine.py -q        # Quiet mode (short)")
    print("📋 python demo_ai_engine.py -h        # Help (short)")
    
    print_demo_step("Direct AI Engine CLI Commands:")
    print("💻 python ai_engine.py auto 'Hello'          # Auto provider selection")
    print("💻 python ai_engine.py autodecide gpt-4 'Hi' # Autodecide for specific model")
    print("💻 python ai_engine.py groq 'Test message'   # Test specific provider")
    print("💻 python ai_engine.py status                # Show engine status")
    print("💻 python ai_engine.py list                  # List all providers")
    print("💻 python ai_engine.py stress                # Run stress test")
    print("💻 python ai_engine.py keys                  # Show key usage stats")
    print("💻 python ai_engine.py server                # Start web server")
    
    print_demo_step("Verbose vs Quiet Mode Differences:")
    print("🔊 VERBOSE MODE:")
    print("   - Shows provider loading details")
    print("   - Displays API call timing and responses")
    print("   - Includes debug information and warnings")
    print("   - Shows detailed engine initialization logs")
    
    print("🔇 QUIET MODE:")
    print("   - Minimal logging for clean output")
    print("   - Focuses on demo content only")
    print("   - Hides provider loading details")
    print("   - Ideal for presentations and quick demos")

def main():
    """
    Main demonstration function - designed to complete in under 10 seconds
    Supports verbose control via command line arguments
    """
    
    # Check for verbose flag without using argparse
    verbose_mode = False
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ['verbose', '-v', '--verbose', 'v']:
            verbose_mode = True
            print_success("🔊 Verbose mode enabled - detailed logging will be shown")
        elif arg in ['quiet', '-q', '--quiet', 'q']:
            verbose_mode = False
            print_info("🔇 Quiet mode enabled - minimal logging")
        elif arg in ['help', '-h', '--help', 'h']:
            print_demo_help()
            return
        else:
            print_warning(f"Unknown argument: {arg}")
            print_info("Available options: verbose, quiet, help")
            print_info("Example: python demo_ai_engine.py verbose")
            return
    
    print("AI Engine v3.0 - Quick Feature Demonstration")
    print("=" * 80)
    print_warning("DEMO MODE: Fast execution optimized for under 10 seconds")
    print_info("This demonstration covers all major features with minimal API calls")
    print_info("Each section shows core functionality with detailed explanations")
    print()
    
    if verbose_mode:
        print_success("🔊 VERBOSE MODE: Detailed logging and provider information enabled")
        print_info("You will see provider loading details and API call information")
    else:
        print_info("🔇 QUIET MODE: Minimal logging for clean demo output")
        print_info("Use 'python demo_ai_engine.py verbose' for detailed logging")
    
    print()
    print_warning("Note: Only ONE real API call will be made to demonstrate live functionality")
    print_info("All other sections use configuration analysis and simulation for speed")
    print_info("For full testing, see comprehensive test files or run server.py")
    print("=" * 80)
    total_start_time = time.time()
    
    try:
        # Section 1: Basic initialization (fast)
        engine = quick_basic_demo(verbose_mode)
        
        # Section 2: Provider overview (no API calls)
        quick_provider_demo(engine)
        
        # Section 3: Autodecide demonstration (simulated)
        quick_autodecide_demo(engine)
        
        # Section 4: Single real API call
        quick_api_demo(engine, verbose_mode)
        
        # Section 5: Feature overview (no API calls)
        quick_features_overview()
        
        # Section 6: Usage examples (no API calls)
        quick_usage_examples()
        
        total_time = time.time() - total_start_time
        
        print_section("Demo Complete - All Features Demonstrated", f"Total execution time: {total_time:.2f} seconds")
        
        print_feature("What you've seen in this demo:")
        print("✅ Engine initialization and configuration management")
        print("✅ Provider management and intelligent categorization")
        print("✅ Autodecide system with model-to-provider matching")
        print("✅ Live API call with automatic provider selection")
        print("✅ Complete feature overview and error handling system")
        print("✅ Practical usage examples and integration patterns")
        
        print(f"\n{'-' * 60}")
        print_feature("📚 Next Steps - Explore More:")
        print("📖 README.md - Complete documentation and setup guide")
        print("🔧 AI_ENGINE_DOCUMENTATION.md - Technical deep-dive and architecture")
        print("🌐 SERVER_README.md - Web server and REST API documentation")
        print("🚀 QUICKSTART.md - Quick setup and first steps guide")
        print()
        print_feature("🛠️  Try These Commands:")
        print("💻 python server.py                    # Start web dashboard")
        print("⚡ python ai_engine.py status          # Show engine status and providers")
        print("🧪 python test_autodecide_basic.py     # Run basic tests")
        print("🔥 python test_autodecide_comprehensive.py # Full test suite")
        
        print(f"\n{'-' * 60}")
        print_success(f"Demo completed in {total_time:.2f} seconds")
        if total_time > 10:
            print_warning("Demo exceeded 10 seconds - consider reducing API calls or improving network speed")
        else:
            print_success("Demo completed within target time of 10 seconds - PERFORMANCE OPTIMAL")
            
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
        print("The demo can be run again at any time")
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        print("This may be due to:")
        print("  - Missing API keys in .env file")
        print("  - Network connectivity issues")
        print("  - Provider service unavailability")
        print("\n💡 Solutions:")
        print("  - Check your .env file has valid API keys")
        print("  - Verify internet connection")
        print("  - Try again later if providers are down")
        print("  - See README.md for troubleshooting guide")

if __name__ == "__main__":
    main()
