#!/usr/bin/env python3
"""
AI Engine CLI - Interactive provider management tool
Add, remove, and configure AI providers interactively
"""
import os
import sys
import json
import re
from pathlib import Path


def print_header():
    print("\n" + "=" * 60)
    print("  AI Engine CLI - Provider Management")
    print("=" * 60 + "\n")


def print_section(title):
    print(f"\n--- {title} ---\n")


def get_input(prompt, default=None, required=False):
    """Get user input with optional default"""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        while True:
            user_input = input(f"{prompt}: ").strip()
            if user_input or not required:
                return user_input
            print("This field is required!")


def get_yes_no(prompt, default=True):
    """Get yes/no confirmation"""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        user_input = input(f"{prompt} {suffix}: ").strip().lower()
        if not user_input:
            return default
        if user_input in ('y', 'yes'):
            return True
        if user_input in ('n', 'no'):
            return False
        print("Please enter y or n")


def test_endpoint(url, timeout=10):
    """Test if an endpoint is reachable"""
    import requests
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code < 500
    except:
        return False


def discover_models(endpoint, api_key=None, auth_type='bearer'):
    """Discover available models from an endpoint"""
    import requests
    try:
        headers = {'Content-Type': 'application/json'}
        if api_key:
            if auth_type == 'bearer':
                headers['Authorization'] = f'Bearer {api_key}'
            elif auth_type == 'api_key':
                headers['X-API-Key'] = api_key

        resp = requests.get(endpoint, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get('data', [])
            return [m.get('id', '') for m in models if m.get('id')]
    except:
        pass
    return []


def validate_url(url):
    """Validate URL format"""
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url))


def add_provider_interactive():
    """Interactive provider addition wizard"""
    print_section("Add New Provider")

    # Basic info
    name = get_input("Provider name (e.g., 'my-provider')", required=True)
    if not name.isalnum() and not all(c.isalnum() or c == '_' for c in name):
        print("Warning: Provider name should contain only letters, numbers, and underscores")

    print("\nAvailable formats: openai, gemini, cohere, a3z_get, cloudflare, ollama, flowith, minimax")
    format_type = get_input("Provider format", default="openai")

    # Endpoint
    print("\n--- Endpoint Configuration ---")
    base_url = get_input("Base URL (e.g., 'https://api.example.com')", required=True)
    if not validate_url(base_url):
        print("Warning: URL doesn't look valid, but continuing anyway")

    endpoint = get_input("Chat endpoint path", default="/v1/chat/completions")
    full_endpoint = base_url.rstrip('/') + endpoint

    model_endpoint = get_input("Models endpoint path (leave empty if none)", default="/v1/models")
    full_model_endpoint = base_url.rstrip('/') + model_endpoint if model_endpoint else None

    # Authentication
    print("\n--- Authentication ---")
    print("Auth types: bearer, api_key, query_param, none")
    auth_type = get_input("Auth type", default="bearer")

    api_key = None
    if auth_type != 'none':
        api_key = get_input("API key (or env var name like 'MY_API_KEY')", required=True)
        # Check if it's an env var reference
        if api_key.isupper() and '_' in api_key:
            env_value = os.getenv(api_key)
            if env_value:
                print(f"  Found value in environment: {api_key}")
            else:
                print(f"  Warning: {api_key} not found in environment")

    # Model
    print("\n--- Model Configuration ---")
    # Try to discover models
    print("Attempting to discover models...")
    models = discover_models(full_model_endpoint, api_key, auth_type)
    if models:
        print(f"Found {len(models)} models:")
        for i, model in enumerate(models[:10], 1):
            print(f"  {i}. {model}")
        if len(models) > 10:
            print(f"  ... and {len(models) - 10} more")

    model = get_input("Default model name", default=models[0] if models else "gpt-4")

    # Limits
    print("\n--- Rate Limits ---")
    rpm_limit = get_input("Requests per minute limit (empty for no limit)", default=None)
    daily_limit = get_input("Daily request limit (empty for no limit)", default=None)

    # Other settings
    print("\n--- Other Settings ---")
    max_tokens = get_input("Max tokens (empty for provider default)", default=None)
    temperature = get_input("Temperature (0-2, empty for default)", default="0.7")
    timeout = get_input("Timeout in seconds", default="60")
    priority = get_input("Priority (1=highest)", default="10")

    # Test the endpoint
    print("\n--- Testing ---")
    if get_yes_no("Test the endpoint now?", default=True):
        print(f"Testing {full_endpoint}...")
        if test_endpoint(full_model_endpoint or full_endpoint):
            print("  Endpoint is reachable!")
        else:
            print("  Warning: Endpoint not reachable (may need API key)")

    # Confirmation
    print("\n--- Configuration Summary ---")
    print(f"Name: {name}")
    print(f"Format: {format_type}")
    print(f"Endpoint: {full_endpoint}")
    print(f"Model: {model}")
    print(f"Auth: {auth_type}")

    if not get_yes_no("\nSave this provider?", default=True):
        print("Cancelled.")
        return

    # Build provider config
    provider_config = {
        "id": get_next_id(),
        "priority": int(priority) if priority else 10,
        "api_keys": [api_key] if api_key else [None],
        "endpoint": full_endpoint,
        "model_endpoint": full_model_endpoint,
        "model_endpoint_auth": bool(api_key),
        "model": model,
        "method": "POST",
        "auth_type": auth_type if auth_type != 'none' else None,
        "max_tokens": int(max_tokens) if max_tokens else None,
        "temperature": float(temperature) if temperature else None,
        "timeout": int(timeout) if timeout else 60,
        "retries": 3,
        "backoff": 5,
        "format": format_type,
        "enabled": True,
        "rpm_limit": int(rpm_limit) if rpm_limit else None,
        "daily_limit": int(daily_limit) if daily_limit else None,
        "current_key_index": 0,
        "consecutive_failures": 0
    }

    # Save to config
    save_provider(name, provider_config)
    print(f"\nProvider '{name}' added successfully!")


def get_next_id():
    """Get next available provider ID"""
    from config import AI_CONFIGS
    if not AI_CONFIGS:
        return 1
    return max(c.get('id', 0) for c in AI_CONFIGS.values()) + 1


def save_provider(name, config):
    """Save provider to config.py"""
    config_path = Path(__file__).parent / "config.py"

    with open(config_path, 'r') as f:
        content = f.read()

    # Format the provider config
    config_str = json.dumps(config, indent=4)
    # Replace JSON format with Python format
    config_str = config_str.replace('true', 'True').replace('false', 'False').replace('null', 'None')

    # Find the insertion point (after last provider)
    # Look for the last closing brace before ENGINE_SETTINGS
    insert_marker = "ENGINE_SETTINGS = {"
    if insert_marker in content:
        # Add the new provider before ENGINE_SETTINGS
        new_provider = f'    "{name}": {config_str},\n'
        content = content.replace(insert_marker, new_provider + "\n" + insert_marker)

        with open(config_path, 'w') as f:
            f.write(content)


def list_providers():
    """List all configured providers"""
    from config import AI_CONFIGS

    print_section("Configured Providers")

    if not AI_CONFIGS:
        print("No providers configured.")
        return

    print(f"{'Name':<15} {'ID':<5} {'Priority':<10} {'Enabled':<10} {'Format':<10}")
    print("-" * 60)

    for name, config in AI_CONFIGS.items():
        enabled = "Yes" if config.get('enabled', True) else "No"
        print(f"{name:<15} {config.get('id', '?'):<5} {config.get('priority', '?'):<10} {enabled:<10} {config.get('format', '?'):<10}")


def test_provider():
    """Test a specific provider"""
    from config import AI_CONFIGS

    print_section("Test Provider")

    name = get_input("Provider name", required=True)
    if name not in AI_CONFIGS:
        print(f"Provider '{name}' not found!")
        return

    config = AI_CONFIGS[name]
    print(f"Testing {name}...")
    print(f"  Endpoint: {config['endpoint']}")

    if test_endpoint(config['endpoint']):
        print("  Status: Reachable!")
    else:
        print("  Status: Not reachable")


def main():
    """Main CLI entry point"""
    print_header()

    while True:
        print("\nOptions:")
        print("  1. List providers")
        print("  2. Add new provider")
        print("  3. Test provider")
        print("  4. Exit")

        choice = input("\nSelect option (1-4): ").strip()

        if choice == '1':
            list_providers()
        elif choice == '2':
            add_provider_interactive()
        elif choice == '3':
            test_provider()
        elif choice == '4':
            print("\nGoodbye!")
            break
        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()
