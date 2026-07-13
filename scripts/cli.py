#!/usr/bin/env python3
"""AI Engine CLI - Provider management tool"""
import re
from pathlib import Path


def print_header():
    print("\n" + "=" * 60)
    print("  AI Engine CLI - Provider Management")
    print("=" * 60)


def get_input(prompt, default=None, required=False):
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    while True:
        user_input = input(f"{prompt}: ").strip()
        if user_input or not required:
            return user_input
        print("Required!")


def get_yes_no(prompt, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        user_input = input(f"{prompt} {suffix}: ").strip().lower()
        if not user_input:
            return default
        if user_input in ('y', 'yes'):
            return True
        if user_input in ('n', 'no'):
            return False


def format_api_key(raw_key):
    """Convert input to proper Python code"""
    if not raw_key:
        return "None"
    if raw_key.isupper() and '_' in raw_key and ' ' not in raw_key:
        return f'os.getenv("{raw_key}")'
    if raw_key.startswith('os.getenv('):
        return raw_key
    return f'"{raw_key}"'


def format_provider(name, config):
    """Format provider as Python dict string"""
    api_keys_str = "[" + ", ".join(config["api_keys"]) + "]"
    model_ep = f'"{config["model_endpoint"]}"' if config.get("model_endpoint") else "None"
    auth_type = f'"{config["auth_type"]}"' if config.get("auth_type") else "None"
    max_tokens = str(config["max_tokens"]) if config.get("max_tokens") else "None"
    rpm = str(config["rpm_limit"]) if config.get("rpm_limit") else "None"
    daily = str(config["daily_limit"]) if config.get("daily_limit") else "None"

    return f'''    "{name}": {{
        "id": {config["id"]}, "priority": {config["priority"]},
        "api_keys": {api_keys_str},
        "endpoint": "{config["endpoint"]}",
        "model_endpoint": {model_ep},
        "model_endpoint_auth": {config.get("model_endpoint_auth", False)},
        "model": "{config["model"]}",
        "method": "POST", "auth_type": {auth_type},
        "max_tokens": {max_tokens},
        "temperature": {config.get("temperature", 0.7)},
        "timeout": {config.get("timeout", 60)},
        "retries": 3, "backoff": 5,
        "format": "{config["format"]}",
        "enabled": bool({config["api_keys"][0]}) if {config["api_keys"][0] != "None"} else False,
        "rpm_limit": {rpm}, "daily_limit": {daily},
        "current_key_index": 0, "consecutive_failures": 0
    }}'''


def save_provider(name, config):
    """Save provider inside AI_CONFIGS dict"""
    config_path = Path(__file__).parent.parent / "config.py"
    with open(config_path, 'r') as f:
        content = f.read()

    # Find the line with closing brace of AI_CONFIGS (before ENGINE_SETTINGS)
    # Pattern: look for "}" that is followed by ENGINE_SETTINGS
    pattern = r'(\n\})(\s*\n\s*ENGINE_SETTINGS)'
    match = re.search(pattern, content)

    if not match:
        print("Error: Could not find AI_CONFIGS end")
        return

    # Insert provider before the closing brace
    insert_pos = match.start()
    provider_code = ",\n" + format_provider(name, config)

    content = content[:insert_pos] + provider_code + content[insert_pos:]

    with open(config_path, 'w') as f:
        f.write(content)


def list_providers():
    import sys
    # Force reload config
    if 'config' in sys.modules:
        del sys.modules['config']
    from config import AI_CONFIGS
    print("\n--- Configured Providers ---\n")
    print(f"{'Name':<15} {'ID':<5} {'Pri':<5} {'Enabled':<8} {'Format':<10}")
    print("-" * 55)
    for name, c in AI_CONFIGS.items():
        enabled = "Yes" if c.get('enabled', True) else "No"
        print(f"{name:<15} {c.get('id','?'):<5} {c.get('priority','?'):<5} {enabled:<8} {c.get('format','?'):<10}")


def add_provider():
    print("\n--- Add New Provider ---\n")
    name = get_input("Provider name", required=True)

    print("\nFormats: openai, gemini, cohere, a3z_get, cloudflare, ollama, flowith, minimax")
    fmt = get_input("Format", default="openai")

    base_url = get_input("Base URL", required=True)
    chat_path = get_input("Chat endpoint path", default="/v1/chat/completions")
    models_path = get_input("Models endpoint path (empty for none)", default="/v1/models")

    full_endpoint = base_url.rstrip('/') + chat_path
    full_models = base_url.rstrip('/') + models_path if models_path else None

    print("\nAuth types: bearer, api_key, query_param, none")
    auth_type = get_input("Auth type", default="bearer")

    raw_key = None
    api_key_code = "None"
    if auth_type != 'none':
        raw_key = get_input("API key (env var name like MY_KEY or actual key)", required=True)
        api_key_code = format_api_key(raw_key)
        print(f"  Stored as: {api_key_code}")

    model = get_input("Default model", default="gpt-4")
    rpm = get_input("RPM limit (empty for none)", default=None)
    daily = get_input("Daily limit (empty for none)", default=None)
    max_tokens = get_input("Max tokens (empty for default)", default=None)
    temp = get_input("Temperature", default="0.7")
    timeout = get_input("Timeout seconds", default="60")
    priority = get_input("Priority (1=highest)", default="10")

    from config import AI_CONFIGS
    next_id = max(c.get('id', 0) for c in AI_CONFIGS.values()) + 1 if AI_CONFIGS else 1

    config = {
        "id": next_id,
        "priority": int(priority),
        "api_keys": [api_key_code],
        "endpoint": full_endpoint,
        "model_endpoint": full_models,
        "model_endpoint_auth": bool(raw_key),
        "model": model,
        "format": fmt,
        "auth_type": auth_type if auth_type != 'none' else None,
        "max_tokens": int(max_tokens) if max_tokens else None,
        "temperature": float(temp),
        "timeout": int(timeout),
        "rpm_limit": int(rpm) if rpm else None,
        "daily_limit": int(daily) if daily else None,
    }

    print(f"\n--- Preview ---\n{format_provider(name, config)}")

    if get_yes_no("Save?"):
        save_provider(name, config)
        print(f"\n'{name}' added!")
    else:
        print("Cancelled.")


def show_status():
    """Show provider status"""
    import requests
    from config import AI_CONFIGS

    print("\n--- Provider Status ---\n")
    print(f"{'Name':<15} {'Status':<10} {'Endpoint'}")
    print("-" * 60)

    for name, config in AI_CONFIGS.items():
        endpoint = config.get('endpoint', '')
        try:
            resp = requests.get(endpoint.replace('/chat/completions', '/models'), timeout=5)
            status = "OK" if resp.status_code < 500 else f"ERR {resp.status_code}"
        except Exception:
            status = "UNREACHABLE"

        print(f"{name:<15} {status:<10} {endpoint[:30]}")


def test_all_providers():
    """Test all providers"""
    import requests
    from config import AI_CONFIGS

    print("\n--- Testing All Providers ---\n")

    passed = 0
    failed = 0

    for name, config in AI_CONFIGS.items():
        models_endpoint = config.get('model_endpoint')

        if models_endpoint:
            try:
                resp = requests.get(models_endpoint, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get('data', [])
                    print(f"  {name}: OK ({len(models)} models)")
                    passed += 1
                else:
                    print(f"  {name}: HTTP {resp.status_code}")
                    failed += 1
            except Exception as e:
                print(f"  {name}: ERROR - {str(e)[:30]}")
                failed += 1
        else:
            print(f"  {name}: No models endpoint")

    print(f"\nResults: {passed} passed, {failed} failed")


def show_stats():
    """Show usage statistics"""
    import requests

    print("\n--- Usage Statistics ---\n")

    try:
        resp = requests.get("http://localhost:8000/api/statistics", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            summary = data.get('summary', {})
            print(f"Total Providers: {summary.get('total_providers', 0)}")
            print(f"Total Requests: {summary.get('total_requests', 0)}")
            print(f"Success Rate: {summary.get('overall_success_rate', 'N/A')}")
        else:
            print("Server not running or statistics unavailable")
    except Exception:
        print("Server not running")


def main():
    print_header()
    while True:
        print("\n  1. List providers")
        print("  2. Add provider")
        print("  3. Provider status")
        print("  4. Test all providers")
        print("  5. Usage stats")
        print("  6. Exit")

        choice = input("\nSelect: ").strip()
        if choice == '1':
            list_providers()
        elif choice == '2':
            add_provider()
        elif choice == '3':
            show_status()
        elif choice == '4':
            test_all_providers()
        elif choice == '5':
            show_stats()
        elif choice == '6':
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
