#!/usr/bin/env python3
"""
Provider Diagnostic Script
Tests all configured providers and shows detailed errors
"""
import requests
import json
import time
from config import AI_CONFIGS
from dotenv import load_dotenv
import os

load_dotenv()

def test_provider(name, config):
    """Test a single provider and return detailed results"""
    result = {
        "name": name,
        "endpoint": config.get("endpoint", ""),
        "model": config.get("model", ""),
        "auth_type": config.get("auth_type"),
        "status": "unknown",
        "error": None,
        "response": None,
        "latency_ms": 0
    }
    
    endpoint = config.get("endpoint", "")
    if not endpoint:
        result["status"] = "no_endpoint"
        result["error"] = "No endpoint configured"
        return result
    
    # Get API key
    api_keys = config.get("api_keys", [])
    actual_key = None
    for key in api_keys:
        if key and not str(key).startswith("os.getenv") and key != "free":
            actual_key = key
            break
    
    # Build headers
    headers = {"Content-Type": "application/json"}
    auth_type = config.get("auth_type")
    
    if auth_type == "bearer":
        if actual_key:
            headers["Authorization"] = f"Bearer {actual_key}"
        elif api_keys and api_keys[0] == "free":
            headers["Authorization"] = "Bearer free"
    
    # Build payload
    payload = {
        "model": config.get("model", "gpt-4"),
        "messages": [{"role": "user", "content": "Say hi"}],
        "max_tokens": 20
    }
    
    # Make request
    start_time = time.time()
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=15)
        result["latency_ms"] = round((time.time() - start_time) * 1000)
        result["status_code"] = response.status_code
        
        if response.status_code == 200:
            try:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                result["status"] = "working"
                result["response"] = content[:50]
            except:
                result["status"] = "parse_error"
                result["error"] = "Could not parse response"
        elif response.status_code == 401:
            result["status"] = "auth_required"
            result["error"] = f"HTTP 401: {response.text[:100]}"
        elif response.status_code == 403:
            result["status"] = "forbidden"
            result["error"] = f"HTTP 403: {response.text[:100]}"
        elif response.status_code == 404:
            result["status"] = "not_found"
            result["error"] = f"HTTP 404: Model or endpoint not found"
        elif response.status_code == 429:
            result["status"] = "rate_limited"
            result["error"] = f"HTTP 429: Rate limited"
        elif response.status_code == 500:
            result["status"] = "server_error"
            result["error"] = f"HTTP 500: {response.text[:100]}"
        else:
            result["status"] = "error"
            result["error"] = f"HTTP {response.status_code}: {response.text[:100]}"
    
    except requests.exceptions.Timeout:
        result["status"] = "timeout"
        result["error"] = "Request timed out (15s)"
    except requests.exceptions.ConnectionError as e:
        result["status"] = "connection_error"
        result["error"] = f"Connection failed: {str(e)[:100]}"
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"Error: {str(e)[:100]}"
    
    return result


def main():
    print("=" * 70)
    print("AI ENGINE - PROVIDER DIAGNOSTIC TOOL")
    print("=" * 70)
    print()
    
    results = []
    
    for name, config in AI_CONFIGS.items():
        if not config.get("enabled", True):
            print(f"⏭️  {name}: DISABLED (skipping)")
            continue
        
        print(f"Testing {name}...", end=" ")
        result = test_provider(name, config)
        results.append(result)
        
        if result["status"] == "working":
            print(f"✅ WORKING ({result['latency_ms']}ms)")
            print(f"   Response: {result['response']}")
        else:
            print(f"❌ {result['status'].upper()}")
            if result["error"]:
                print(f"   Error: {result['error']}")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    working = [r for r in results if r["status"] == "working"]
    failed = [r for r in results if r["status"] != "working"]
    
    print(f"\n✅ Working: {len(working)}/{len(results)}")
    for r in working:
        print(f"   {r['name']} ({r['latency_ms']}ms)")
    
    print(f"\n❌ Failed: {len(failed)}/{len(results)}")
    
    # Group by error type
    by_error = {}
    for r in failed:
        status = r["status"]
        if status not in by_error:
            by_error[status] = []
        by_error[status].append(r["name"])
    
    for status, names in by_error.items():
        print(f"\n   {status.upper()}:")
        for name in names:
            next(r for r in results if r["name"] == name)
            error = next(r for r in results if r["name"] == name)["error"]
            print(f"     - {name}: {error[:60] if error else 'No error message'}")


if __name__ == "__main__":
    main()
