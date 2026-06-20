#!/usr/bin/env python3
"""
Provider Diagnostic Script with Retry Mechanism
Tests all configured providers and shows detailed errors
"""
import requests
import json
import time
from config import AI_CONFIGS
from dotenv import load_dotenv
import os

load_dotenv()

def test_provider(name, config, max_retries=2, retry_delay=2):
    """Test a single provider with retry mechanism"""
    result = {
        "name": name,
        "endpoint": config.get("endpoint", ""),
        "model": config.get("model", ""),
        "auth_type": config.get("auth_type"),
        "status": "unknown",
        "error": None,
        "response": None,
        "latency_ms": 0,
        "retries": 0
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
    
    # Handle Cloudflare special format
    if "cloudflare" in name.lower() or "cf" in name.lower():
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        if account_id:
            endpoint = endpoint.format(account_id=account_id, model=config.get("model", ""))
            payload = {"messages": [{"role": "user", "content": "Say hi"}]}
    
    # Retry loop
    for attempt in range(max_retries + 1):
        result["retries"] = attempt
        
        start_time = time.time()
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=15)
            result["latency_ms"] = round((time.time() - start_time) * 1000)
            result["status_code"] = response.status_code
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Handle Cloudflare wrapped response
                    result_data = data.get("result", data)
                    content = result_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    result["status"] = "working"
                    result["response"] = content[:50]
                    return result
                except:
                    result["status"] = "parse_error"
                    result["error"] = "Could not parse response"
                    return result
            elif response.status_code == 429:
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                result["status"] = "rate_limited"
                result["error"] = f"HTTP 429: Rate limited after {max_retries} retries"
                return result
            elif response.status_code == 401:
                result["status"] = "auth_required"
                result["error"] = f"HTTP 401: {response.text[:100]}"
                return result
            elif response.status_code == 403:
                result["status"] = "forbidden"
                result["error"] = f"HTTP 403: {response.text[:100]}"
                return result
            elif response.status_code == 404:
                result["status"] = "not_found"
                result["error"] = f"HTTP 404: {response.text[:100]}"
                return result
            else:
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                result["status"] = "error"
                result["error"] = f"HTTP {response.status_code}: {response.text[:100]}"
                return result
        
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            result["status"] = "timeout"
            result["error"] = f"Timeout after {max_retries} retries"
            return result
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            result["status"] = "connection_error"
            result["error"] = f"Connection failed: {str(e)[:100]}"
            return result
        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            result["status"] = "error"
            result["error"] = f"Error: {str(e)[:100]}"
            return result
    
    return result


def main():
    print("=" * 70)
    print("AI ENGINE - PROVIDER DIAGNOSTIC TOOL (with retries)")
    print("=" * 70)
    print()
    
    results = []
    
    for name, config in AI_CONFIGS.items():
        if not config.get("enabled", True):
            print(f"  {name}: DISABLED (skipping)")
            continue
        
        print(f"Testing {name}...", end=" ", flush=True)
        result = test_provider(name, config, max_retries=2, retry_delay=1)
        results.append(result)
        
        if result["status"] == "working":
            retries = result["retries"]
            retry_str = f" (retries: {retries})" if retries > 0 else ""
            print(f"WORKING ({result['latency_ms']}ms{retry_str})")
        else:
            retries = result["retries"]
            retry_str = f" (retries: {retries})" if retries > 0 else ""
            print(f"{result['status'].upper()}{retry_str}")
            if result["error"]:
                print(f"   Error: {result['error'][:60]}")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    working = [r for r in results if r["status"] == "working"]
    failed = [r for r in results if r["status"] != "working"]
    
    print(f"\n  Working: {len(working)}/{len(results)}")
    for r in sorted(working, key=lambda x: x["latency_ms"]):
        retries = r["retries"]
        retry_str = f" (retries: {retries})" if retries > 0 else ""
        print(f"    {r['name']}: {r['latency_ms']}ms{retry_str}")
    
    print(f"\n  Failed: {len(failed)}/{len(results)}")
    
    # Group by error type
    by_error = {}
    for r in failed:
        status = r["status"]
        if status not in by_error:
            by_error[status] = []
        by_error[status].append(r)
    
    for status, items in by_error.items():
        print(f"\n  {status.upper()}:")
        for r in items:
            retries = r["retries"]
            retry_str = f" (retries: {retries})" if retries > 0 else ""
            print(f"    - {r['name']}{retry_str}: {r['error'][:50] if r['error'] else 'No error'}")


if __name__ == "__main__":
    main()
