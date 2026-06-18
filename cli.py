#!/usr/bin/env python3
"""
AI Engine CLI - Interactive provider management tool
"""
import os
import sys
import re
from pathlib import Path


def print_header():
    print("\n" + "=" * 60)
    print("  AI Engine CLI - Provider Management")
    print("=" * 60)


def print_section(title):
    print(f"\n--- {title} ---\n")


def get_input(prompt, default=None, required=False):
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
    import requests
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code < 500
    except:
        return False


def discover_models(endpoint, api_key=None, auth_type='bearer'):
    import requests
    try:
        headers = {'Content-Type': 'application/json'}
        if api_key and auth_type == 'bearer':
            headers['Authorization'] = f'Bearer {api_key}'
        resp = requests.get(endpoint, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get('data', [])
            return [m.get('id', '') for m in models if m.get('id')]
    except:
        pass
    return []


def validate_url(url):
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url))


def format_api_key(raw_key):
    """Convert raw input to proper Python code for config.py"""
    if not raw_key:
        return "None"
    
    # If it looks like an env var name (UPPER_CASE with underscores)
    if raw_key.isupper() and '_' in raw_key and ' ' not in raw_key:
        return f'os.getenv("{raw_key}")'
    
    # If it starts with os.getenv already
    if raw_key.startswith('os.getenv('):
        return raw_key
    
    # Otherwise treat as literal value
    return f'"{raw_key}"'


def format_provider_config(name, config):
    """Format provider config as valid Python dict string"""
    lines = [f'    "{name}": {{']
    
    fields = [
        ("id", config["id"], False),
        ("priority", config["priority"], False),
        ("api_keys", config["api_keys"], True),
        ("endpoint", config["endpoint"], True),
        ("model_endpoint", config.get("model_endpoint"), True),
        ("model_endpoint_auth", config.get("model_endpoint_auth", False), False),
        ("model", config["model"], True),
        ("method", config.get("method", "POST"), True),
        ("auth_type", config.get("auth_type"), True),
        ("max_tokens", config.get("max_tokens"), False),
        ("temperature", config.get("temperature"), False),
        ("timeout", config.get("timeout", 60), False),
        ("retries", config.get("retries", 3), False),
        ("backoff", config.get("backoff", 5), False),
        ("format", config["format"], True),
        ("enabled", config.get("enabled", True), False),
        ("rpm_limit", config.get("rpm_limit"), False),
        ("daily_limit", config.get("daily_limit"), False),
        ("current_key_index", 0, False),
        ("consecutive_failures", 0, False),
    ]
    
    for i, (key, value, is_string) in enumerate(fields):
        comma = "," if i < len(fields) - 1 else ""
        
        if value is None:
            formatted = "None"
        elif is_string:
            formatted = f'"{value}"'
        elif isinstance(value, bool):
            formatted = "True" if value else "False"
        elif isinstance(value, (int, float)):
            formatted = str(value)
        else:
            formatted = f'"{value}"'
        
        # Special handling for api_keys (it's a list with os.getenv calls)
        if key == "api_keys" and isinstance(value, list):
            formatted = "[" + ", ".join(value) + "]"
        
        lines.append(f'        "{key}": {formatted}{comma}')
    
    lines.append('    }')
    return "\n".join(lines)


def add_provider_interactive():
    print_section("Add New Provider")

    name = get_input("Provider name (e.g., 'my_provider')", required=True)
    
    print("\nFormats: openai, gemini, cohere, a3z_get, cloudflare, ollama, flowith, minimax")
    format_type = get_input("Provider format", default="openai")

    print("\n--- Endpoint ---")
    base_url = get_input("Base URL (e.g., 'https://api.example.com')", required=True)
    
    chat_path = get_input("Chat endpoint path", default="/v1/chat/completions")
    full_endpoint = base_url.rstrip('/') + chat_path
    
    models_path = get_input("Models endpoint path (empty if none)", default="/v1/models")
    full_models_endpoint = base_url.rstrip('/') + models_path if models_path else None

    print("\n--- Authentication ---")
    print("Auth types: bearer, api_key, query_param, none")
    auth_type = get_input("Auth type", default="bearer")
    
    raw_api_key = None
    api_key_code = "None"
    if auth_type != 'none':
        raw_api_key = get_input(
            "API key (env var name like 'MY_API_KEY' or actual key)", 
            required=True
        )
        api_key_code = format_api_key(raw_api_key)
        print(f"  Will be stored as: {api_key_code}")

    print("\n--- Model ---")
    print("Attempting to discover models...")
    models = discover_models(full_models_endpoint, raw_api_key, auth_type)
    if models:
        print(f"Found {len(models)} models:")
        for i, model in enumerate(models[:10], 1):
            print(f"  {i}. {model}")
        if len(models) > 10:
            print(f"  ... and {len(models) - 10} more")
    
    model = get_input("Default model", default=models[0] if models else "gpt-4")

    print("\n--- Limits ---")
    rpm_limit = get_input("RPM limit (empty for none)", default=None)
    daily_limit = get_input("Daily limit (empty for none)", default=None)
    max_tokens = get_input("Max tokens (empty for default)", default=None)
    temperature = get_input("Temperature (0-2)", default="0.7")
    timeout = get_input("Timeout seconds", default="60")
    priority = get_input("Priority (1=highest)", default="10")

    # Build config
    config = {
        "id": get_next_id(),
        "priority": int(priority),
        "api_keys": [api_key_code],
        "endpoint": full_endpoint,
        "model_endpoint": full_models_endpoint,
        "model_endpoint_auth": bool(raw_api_key),
        "model": model,
        "method": "POST",
        "auth_type": auth_type if auth_type != 'none' else None,
        "max_tokens": int(max_tokens) if max_tokens else None,
        "temperature": float(temperature),
        "timeout": int(timeout),
        "retries": 3,
        "backoff": 5,
        "format": format_type,
        "enabled": True,
        "rpm_limit": int(rpm_limit) if rpm_limit else None,
        "daily_limit": int(daily_limit) if daily_limit else None,
        "current_key_index": 0,
        "consecutive_failures": 0,
    }

    # Show preview
    print("\n--- Preview ---")
    print(format_provider_config(name, config))

    if not get_yes_no("\nSave this provider?", default=True):
        print("Cancelled.")
        return

    save_provider(name, config)
    print(f"\nProvider '{name}' added successfully!")


def get_next_id():
    from config import AI_CONFIGS
    if not AI_CONFIGS:
        return 1
    return max(c.get('id', 0) for c in AI_CONFIGS.values()) + 1


def save_provider(name, config):
    config_path = Path(__file__).parent / "config.py"
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Find insertion point - right before "ENGINE_SETTINGS = {"
    marker = '\nENGINE_SETTINGS = {'
    if marker not in content:
        print("Error: Could not find ENGINE_SETTINGS in config.py")
        return
    
    # Format the provider
    provider_block = format_provider_config(name, config) + ",\n"
    
    # Insert before ENGINE_SETTINGS
    content = content.replace(marker, "\n" + provider_block + marker)
    
    with open(config_path, 'w') as f:
        f.write(content)


def list_providers():
    from config import AI_CONFIGS
    print_section("Configured Providers")
    
    if not AI_CONFIGS:
        print("No providers configured.")
        return
    
    print(f"{'Name':<15} {'ID':<5} {'Pri':<5} {'Enabled':<8} {'Format':<10} {'Endpoint'}")
    print("-" * 80)
    
    for name, config in AI_CONFIGS.items():
        enabled = "Yes" if config.get('enabled', True) else "No"
        endpoint = config.get('endpoint', '')[:30]
        print(f"{name:<15} {config.get('id', '?'):<5} {config.get('priority', '?'):<5} {enabled:<8} {config.get('format', '?'):<10} {endpoint}")


def test_provider():
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
    print_header()
    
    while True:
        print("\nOptions:")
        print("  1. List providers")
        print("  2. Add new provider")
        print("  3. Test provider")
        print("  4. Exit")
        
        choice = input("\nSelect (1-4): ").strip()
        
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
            print("Invalid option.")


if __name__ == "__main__":
    main()
