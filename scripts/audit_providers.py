#!/usr/bin/env python3
"""Audit all enabled providers' model endpoints"""
import requests
import os
import sys
import time
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv()
from config import AI_CONFIGS  # noqa: E402

print("=== Provider Model Endpoint Audit ===\n")

results = {"ok": [], "no_endpoint": [], "error": [], "timeout": []}

for name, config in sorted(AI_CONFIGS.items(), key=lambda x: x[1].get('id', 99)):
    if not config.get('enabled', True):
        continue

    endpoint = config.get('model_endpoint')
    auth = config.get('auth_type')
    has_key = any(k for k in config.get('api_keys', []) if k)

    if not endpoint:
        print(f"  {name:20s} NO_ENDPOINT")
        results["no_endpoint"].append(name)
        continue

    headers = {"Content-Type": "application/json"}
    if auth in ("bearer", "bearer_lowercase") and has_key:
        keys = [k for k in config['api_keys'] if k]
        headers["Authorization"] = f"Bearer {keys[0]}"

    try:
        start = time.time()
        resp = requests.get(endpoint, headers=headers, timeout=8)
        elapsed = time.time() - start
        if resp.status_code == 200:
            data = resp.json()
            models = []
            if isinstance(data, list):
                models = data
            elif isinstance(data, dict):
                models = data.get("data", [])
            if len(models) > 0:
                sample = [m.get("id", "?") for m in models[:2]]
                print(f"  {name:20s} OK  {len(models):4d} models  ({elapsed:.1f}s)  {', '.join(sample)}")
                results["ok"].append(name)
            else:
                print(f"  {name:20s} OK  keys={list(data.keys())[:3]}  ({elapsed:.1f}s)")
                results["ok"].append(name)
        else:
            print(f"  {name:20s} ERR HTTP {resp.status_code}  ({elapsed:.1f}s)")
            results["error"].append(name)
    except requests.exceptions.Timeout:
        print(f"  {name:20s} TIMEOUT")
        results["timeout"].append(name)
    except Exception as e:
        print(f"  {name:20s} ERROR {str(e)[:50]}")
        results["error"].append(name)

print("\n=== Summary ===")
print(f"  OK:          {len(results['ok'])}")
print(f"  No endpoint: {len(results['no_endpoint'])}")
print(f"  Error:       {len(results['error'])}")
print(f"  Timeout:     {len(results['timeout'])}")
print(f"  Failed:      {results['error'] + results['timeout']}")
