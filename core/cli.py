"""
CLI module for AI Engine — extracted from ai_engine.py main().
Provides command-line interface for testing and managing providers.
"""
import sys
import atexit
import logging

from core.ai_engine import AI_engine

logger = logging.getLogger(__name__)


def main():
    """Test the AI Engine with command-line support."""
    engine = None

    def cleanup():
        """Save statistics on exit"""
        if engine:
            try:
                engine.save_statistics_now()
            except Exception:
                pass

    atexit.register(cleanup)

    if len(sys.argv) > 1:
        provider_name = sys.argv[1].lower()

        if provider_name == "stress":
            engine = AI_engine(verbose=True)
            print("🧪 Running comprehensive stress test...")
            engine.stress_test_providers(test_iterations=3, ask_for_priority_change=True)
            return

        elif provider_name == "server":
            print("🚀 Starting AI Engine FastAPI Server...")
            try:
                from ai_engine.server.app import main as server_main
                server_main()
            except ImportError as e:
                print(f"❌ Server module not found: {e}")
                print("Install server extras: pip install ai-synapse[server]")
            return

        elif provider_name == "list":
            engine = AI_engine(verbose=False)
            print("📋 Available Providers:")
            sorted_providers = sorted(engine.providers.items(), key=lambda x: x[1]['priority'])
            for i, (name, config) in enumerate(sorted_providers, 1):
                priority = config.get('priority', 999)
                model = config.get('model', 'Unknown')[:30]
                status = "🔑" if engine._get_current_api_key(name) else "🚫"
                print(f"{i:2d}. {name:15} | Priority: {priority:2d} | {status} | {model}")
            return

        elif provider_name == "status":
            engine = AI_engine(verbose=False)
            status = engine.get_status()
            print("📊 Engine Status:")
            print(f"Available providers: {status['available_providers']}/{status['total_providers']}")
            print(f"Top 5 providers: {', '.join(status['available_provider_list'])}")
            if status['flagged_provider_list']:
                print(f"Flagged providers: {', '.join(status['flagged_provider_list'])}")
            return

        elif provider_name == "keys":
            engine = AI_engine(verbose=False)
            if len(sys.argv) > 2:
                target_provider = sys.argv[2].lower()
                if target_provider in engine.providers:
                    print(f"🔑 Key Usage Report for {target_provider}:")
                    print("-" * 50)
                    report = engine.get_key_usage_report(target_provider)
                    if report:
                        for key_name, stats in report.items():
                            print(f"{key_name}:")
                            print(f"  📊 Requests: {stats['total_requests']} (this minute: {stats['requests_this_minute']})")
                            print(f"  ✅ Success Rate: {stats['success_rate']:.1f}%")
                            print(f"  ⚖️  Load Weight: {stats['weight']:.2f}")
                            print(f"  🚦 Rate Limited: {'Yes' if stats['rate_limited'] else 'No'}")
                            print(f"  ⏰ Last Used: {stats['last_used'] or 'Never'}")
                            print()
                    else:
                        print(f"No key data available for {target_provider}")
                else:
                    print(f"Provider '{target_provider}' not found")
            else:
                print("🔑 Key Usage Summary for Multi-Key Providers:")
                print("-" * 60)
                for provider_name, config in engine.providers.items():
                    api_keys = config.get('api_keys', [])
                    valid_keys = [k for k in api_keys if k is not None]
                    if len(valid_keys) > 1:
                        report = engine.get_key_usage_report(provider_name)
                        if report:
                            print(f"📈 {provider_name} ({len(valid_keys)} keys):")
                            for key_name, stats in report.items():
                                status = "🔴 RATE LIMITED" if stats['rate_limited'] else "🟢 ACTIVE"
                                print(f"  {key_name}: {stats['total_requests']} requests, {stats['success_rate']:.1f}% success {status}")
                            print()
            return

        elif provider_name == "auto":
            engine = AI_engine(verbose=True)
            custom_message = "Hello! Please respond with a short test message to verify the system is working."
            if len(sys.argv) > 2:
                custom_message = " ".join(sys.argv[2:])

            print("🔄 Testing automatic provider rotation...")
            print("-" * 50)

            messages = [{"role": "user", "content": custom_message}]
            result = engine.chat_completion(messages)

            if result.success:
                print("✅ AUTO ROTATION SUCCESS!")
                print(f"💬 Response: {result.content}")
                print(f"🏃‍♂️ Provider used: {result.provider_used}")
                print(f"⏱️ Response time: {result.response_time:.2f}s")
            else:
                print("❌ AUTO ROTATION FAILED!")
                print(f"🚨 Error: {result.error_message}")
                print(f"🔍 Error type: {result.error_type}")
            return

        elif provider_name == "autodecide":
            engine = AI_engine()
            if len(sys.argv) < 3:
                print("❌ Usage: python -m core.cli autodecide <model_name> [message]")
                print("📋 Examples:")
                print("   python -m core.cli autodecide gpt-4 'Hello world'")
                print("   python -m core.cli autodecide claude 'Test message'")
                return

            target_model = sys.argv[2]
            custom_message = "Hello! Please respond with a short test message."
            if len(sys.argv) > 3:
                custom_message = " ".join(sys.argv[3:])

            print(f"🎯 Testing autodecide for model: {target_model}")
            print("-" * 50)

            providers = engine._discover_model_providers(target_model)
            if providers:
                print(f"📋 Found {len(providers)} providers supporting '{target_model}':")
                for i, (pname, pmodel) in enumerate(providers[:5], 1):
                    print(f"  {i}. {pname}: {pmodel}")
                if len(providers) > 5:
                    print(f"     ... and {len(providers) - 5} more providers")
            else:
                print(f"⚠️  No providers found for model '{target_model}'")
                print("🔄 Falling back to automatic provider selection...")

            print("\n🚀 Making autodecide chat completion...")
            messages = [{"role": "user", "content": custom_message}]
            result = engine.chat_completion(messages, model=target_model, autodecide=True)

            if result.success:
                print("✅ AUTODECIDE SUCCESS!")
                print(f"🎯 Requested model: {target_model}")
                print(f"🏃‍♂️ Provider selected: {result.provider_used}")
                print(f"🤖 Model used: {result.model_used}")
                print(f"💬 Response: {result.content}")
                print(f"⏱️ Response time: {result.response_time:.2f}s")
            else:
                print("❌ AUTODECIDE FAILED!")
                print(f"🎯 Requested model: {target_model}")
                print(f"🚨 Error: {result.error_message}")
                print(f"🔍 Error type: {result.error_type}")
            return

        # Test specific provider
        engine = AI_engine(verbose=True)
        custom_message = None
        if len(sys.argv) > 2:
            custom_message = " ".join(sys.argv[2:])

        print(f"🎯 Testing specific provider: {provider_name}")
        print("-" * 50)

        result = engine.test_specific_provider(provider_name, custom_message)

        if result.success:
            print(f"✅ {provider_name.upper()} SUCCESS!")
            print(f"💬 Response: {result.content}")
            print(f"⏱️ Response time: {result.response_time:.2f}s")
        else:
            print(f"❌ {provider_name.upper()} FAILED!")
            print(f"🚨 Error: {result.error_message}")
            print(f"🔍 Error type: {result.error_type}")

        return

    # Default behavior - test with priority selection
    engine = AI_engine(verbose=True)

    print("🧪 Testing AI Engine v3.0...")

    messages = [
        {"role": "user", "content": "Hello! Please respond with a short greeting."}
    ]

    result = engine.chat_completion(messages)

    if result.success:
        print(f"✅ Success! Response: {result.content}")
        print(f"🏃‍♂️ Provider used: {result.provider_used}")
        print(f"⏱️ Response time: {result.response_time:.2f}s")
    else:
        print(f"❌ Failed: {result.error_message}")

    status = engine.get_status()
    print("\n📊 Engine Status:")
    print(f"Available providers: {status['available_providers']}/{status['total_providers']}")
    print(f"Top providers: {', '.join(status['available_provider_list'])}")

    print("\n💡 Usage:")
    print("  python -m core.cli                    # Test with priority selection")
    print("  python -m core.cli <provider>         # Test specific provider")
    print("  python -m core.cli <provider> <msg>   # Test with custom message")
    print("  python -m core.cli list               # List all providers")
    print("  python -m core.cli status             # Show engine status")
    print("  python -m core.cli keys               # Show key usage for all providers")
    print("  python -m core.cli keys <provider>    # Show detailed key usage for provider")
    print("  python -m core.cli stress             # Run stress test")
    print("  python -m core.cli server             # Start FastAPI web server")


if __name__ == "__main__":
    main()
