"""
CDN Config Sync — fetches latest provider config from a CDN at startup.
Caches locally with configurable TTL. Falls back to local config on failure.

Environment variables:
    CDN_CONFIG_URL       URL to config.py. Set to "default" for jsDelivr auto-URL, or any raw URL. Empty = disabled.
    CDN_CONFIG_TTL       Cache TTL in seconds (default: 86400 = 24h)
    CDN_CONFIG_BRANCH    Git branch for default jsDelivr URL (default: main)
"""
import os
import sys
import time
import hashlib
import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_CDN_TEMPLATE = "https://cdn.jsdelivr.net/gh/{repo}@{branch}/config.py"
DEFAULT_REPO = "mihir0209/AI_engine"
DEFAULT_TTL = 86400

try:
    from core.user_paths import USER_DATA_DIR

    CACHE_DIR = USER_DATA_DIR
except ImportError:
    CACHE_DIR = Path("data")

CACHE_FILE = CACHE_DIR / "cdn_config_cache.py"
CACHE_META = CACHE_DIR / "cdn_config_meta.json"
LOCK_FILE = CACHE_DIR / "cdn_config.lock"
CACHE_DIR.mkdir(exist_ok=True)


class ConfigFetcher:
    def __init__(self):
        self._lock = threading.Lock()
        self._enabled = False
        self._url: Optional[str] = None
        self._ttl: int = DEFAULT_TTL
        self._branch: str = "main"
        self._fetched_configs: Optional[Dict[str, Any]] = None

    def initialize(self):
        """Initialize from environment variables. Called once at startup."""
        raw_url = os.getenv("CDN_CONFIG_URL", "").strip()

        if not raw_url:
            logger.info("CDN config sync disabled (CDN_CONFIG_URL not set)")
            return

        if raw_url.lower() == "default":
            self._branch = os.getenv("CDN_CONFIG_BRANCH", "main")
            self._url = DEFAULT_CDN_TEMPLATE.format(repo=DEFAULT_REPO, branch=self._branch)
        else:
            self._url = raw_url

        self._ttl = int(os.getenv("CDN_CONFIG_TTL", str(DEFAULT_TTL)))
        self._enabled = True
        logger.info(f"CDN config sync enabled: {self._url} (TTL: {self._ttl}s)")

    def fetch_and_apply(self) -> Optional[Dict[str, Any]]:
        """Fetch config from CDN, cache it, and return the AI_CONFIGS dict.
        Returns None if disabled, failed, or cache is still valid.
        """
        if not self._enabled:
            return None

        with self._lock:
            # Check if cache is still valid
            cached = self._load_cache()
            if cached is not None:
                logger.info("Using cached CDN config (TTL not expired)")
                return cached

            # Fetch from CDN
            fetched = self._fetch_from_cdn()
            if fetched is not None:
                self._save_cache(fetched)
                return fetched

            # Fetch failed — try expired cache as last resort
            expired = self._load_cache(ignore_ttl=True)
            if expired is not None:
                logger.warning("CDN fetch failed, using expired cache")
                return expired

            logger.warning("CDN fetch failed and no cache available, using local config")
            return None

    def _fetch_from_cdn(self) -> Optional[Dict[str, Any]]:
        """Fetch and parse config from CDN URL"""
        import requests

        # Prevent concurrent fetches via lock file
        try:
            if LOCK_FILE.exists():
                lock_age = time.time() - LOCK_FILE.stat().st_mtime
                if lock_age < 60:
                    logger.warning("Another CDN fetch is in progress, skipping")
                    return None
            LOCK_FILE.write_text(str(os.getpid()))
        except Exception:
            pass

        try:
            resp = requests.get(self._url, timeout=15, headers={"User-Agent": f"AI-Engine/{os.getenv('AI_ENGINE_VERSION', '3.0.0')}"})
            if resp.status_code != 200:
                logger.warning(f"CDN fetch failed: HTTP {resp.status_code}")
                return None

            content = resp.text
            configs = self._parse_config(content)
            if configs is None:
                logger.warning("CDN config parse failed — invalid syntax")
                return None

            logger.info(f"CDN fetch successful: {len(configs)} providers")
            return configs

        except requests.exceptions.Timeout:
            logger.warning("CDN fetch timed out")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("CDN fetch connection error (offline?)")
            return None
        except Exception as e:
            logger.warning(f"CDN fetch error: {e}")
            return None
        finally:
            try:
                LOCK_FILE.unlink(missing_ok=True)
            except Exception:
                pass

    def _parse_config(self, content: str) -> Optional[Dict[str, Any]]:
        """Safely parse AI_CONFIGS from raw Python source code.
        Only extracts the AI_CONFIGS dict — skips class definitions and other code.
        """
        try:
            # Find AI_CONFIGS = { ... } block
            marker = "AI_CONFIGS"
            start = content.find(f"{marker} = {{")
            if start == -1:
                return None

            # Find the matching closing brace
            brace_depth = 0
            in_string = False
            string_char = None
            block_start = content.index("{", start)
            end = block_start

            for i in range(block_start, len(content)):
                ch = content[i]
                if in_string:
                    if ch == string_char and content[i-1:i] != "\\":
                        in_string = False
                elif ch in ('"', "'"):
                    # Check for triple quotes
                    if content[i:i+3] in ('"""', "'''"):
                        in_string = True
                        string_char = content[i:i+3]
                        end = i + 3
                    else:
                        in_string = True
                        string_char = ch
                elif ch == "{":
                    brace_depth += 1
                elif ch == "}":
                    brace_depth -= 1
                    if brace_depth == 0:
                        end = i + 1
                        break

            dict_str = content[block_start:end]

            # Execute just the dict definition — only os.getenv allowed (no file/network access)
            import types
            safe_os = types.ModuleType("os")
            safe_os.getenv = os.getenv
            safe_builtins = {
                "True": True, "False": False, "None": None,
                "int": int, "str": str, "float": float, "bool": bool,
                "list": list, "dict": dict, "tuple": tuple,
            }
            namespace = {"__builtins__": safe_builtins, "os": safe_os}
            exec(f"AI_CONFIGS = {dict_str}", namespace)
            configs = namespace.get("AI_CONFIGS")

            if isinstance(configs, dict) and len(configs) > 0:
                for name, cfg in configs.items():
                    if not isinstance(cfg, dict):
                        return None
                    for required in ("id", "endpoint", "model"):
                        if required not in cfg:
                            return None
                return configs
            return None
        except Exception as e:
            logger.warning(f"CDN config parse error: {e}")
            return None

    def _save_cache(self, configs: Dict[str, Any]):
        """Save fetched configs and metadata to cache files"""
        try:
            import json
            meta = {
                "url": self._url,
                "fetched_at": time.time(),
                "ttl": self._ttl,
                "provider_count": len(configs),
                "provider_names": sorted(configs.keys()),
            }
            CACHE_META.write_text(json.dumps(meta, indent=2))

            # Save as JSON for safe re-loading (avoid repr issues with os.getenv)
            cache_data = json.dumps(configs, indent=2)
            CACHE_FILE.write_text(
                f"# Auto-generated CDN config cache\n"
                f"# Source: {self._url}\n"
                f"# Fetched at: {time.ctime()}\n"
                f"# TTL: {self._ttl}s\n"
                f"# DO NOT EDIT — will be overwritten on next CDN refresh\n\n"
                f"import json\n"
                f"AI_CONFIGS = json.loads({repr(cache_data)})\n"
            )
            logger.info(f"CDN config cached to {CACHE_FILE}")
        except Exception as e:
            logger.warning(f"Failed to save CDN cache: {e}")

    def _load_cache(self, ignore_ttl: bool = False) -> Optional[Dict[str, Any]]:
        """Load config from cache if valid (not expired)"""
        try:
            import json
            if not CACHE_META.exists():
                return None

            meta = json.loads(CACHE_META.read_text())
            fetched_at = meta.get("fetched_at", 0)
            ttl = meta.get("ttl", self._ttl)

            if not ignore_ttl and (time.time() - fetched_at) > ttl:
                return None  # Expired

            if not CACHE_FILE.exists():
                return None

            content = CACHE_FILE.read_text()
            # Try JSON-based cache first (new format)
            if "json.loads" in content:
                import json as _json
                start = content.find("json.loads(")
                if start != -1:
                    json_start = content.find("(", start) + 1
                    json_end = content.rfind(")")
                    json_str = content[json_start:json_end]
                    configs = _json.loads(eval(json_str))
                    if isinstance(configs, dict) and len(configs) > 0:
                        return configs
                return None
            # Fallback: old exec-based format
            import builtins
            safe_builtins = {
                name: getattr(builtins, name)
                for name in ("True", "False", "None", "int", "str", "float", "bool",
                             "list", "dict", "tuple", "set", "len", "range", "isinstance",
                             "print", "Exception", "ValueError", "TypeError", "KeyError")
            }
            namespace = {"__builtins__": safe_builtins, "os": os}
            exec(compile(content, "<cdn_cache>", "exec"), namespace)
            configs = namespace.get("AI_CONFIGS")
            if isinstance(configs, dict) and len(configs) > 0:
                return configs
            return None

        except Exception as e:
            logger.warning(f"CDN cache load error: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        try:
            import json
            if not CACHE_META.exists():
                return {"enabled": self._enabled, "url": self._url, "cached": False}
            meta = json.loads(CACHE_META.read_text())
            age = time.time() - meta.get("fetched_at", 0)
            return {
                "enabled": self._enabled,
                "url": self._url,
                "cached": True,
                "cached_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(meta.get("fetched_at", 0))),
                "age_seconds": int(age),
                "ttl": meta.get("ttl", self._ttl),
                "remaining": max(0, meta.get("ttl", self._ttl) - int(age)),
                "providers": meta.get("provider_count", 0),
            }
        except Exception:
            return {"enabled": self._enabled, "url": self._url, "cached": False}


# Global instance
config_fetcher = ConfigFetcher()
