import os
import time
import asyncio
import aiohttp
import requests
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import random
import logging
from dotenv import load_dotenv
from dataclasses import dataclass

# Import configuration from external config file
try:
    from config import AI_CONFIGS, ENGINE_SETTINGS
except ImportError as e:
    print(f"Failed to import from config: {e}")
    print("Falling back to inline configuration...")
    AI_CONFIGS = {}
    ENGINE_SETTINGS = {"key_rotation_enabled": True, "provider_rotation_enabled": True, "consecutive_failure_limit": 5}

# Load environment variables
load_dotenv()

@dataclass
class RequestResult:
    """Result of an AI request"""
    success: bool
    content: str = ""
    status_code: int = 0
    response_time: float = 0.0
    error_message: str = ""
    error_type: str = "unknown"
    provider_used: str = ""
    raw_response: Optional[Dict] = None

class AI_engine:
    """
    Clean AI Engine v3.0 with Python-based configuration and smart key rotation
    """
    
    def __init__(self, verbose: bool = False):
        """Initialize the AI Engine v3.0 with external configuration and advanced features"""
        self.verbose = verbose
        self.logger = self._setup_logging()
        
        # Load configuration from external config file
        self.providers = self._load_enabled_providers()
        self.engine_settings = ENGINE_SETTINGS
        
        # Advanced provider management
        self.flagged_keys = {}  # Track flagged keys with timing
        self.usage_stats = {}   # Track usage statistics
        self.provider_key_rotation = {}  # Track current key index for each provider
        self.consecutive_failures = {}   # Track consecutive failures per provider
        self.current_provider = None
        
        # Enhanced tracking for intelligent key rotation
        self.key_usage_stats = {}  # Track usage per key
        self.key_last_used = {}    # Track last usage time per key
        self.key_request_count = {} # Track requests per key per minute
        
        # Initialize comprehensive stats for all providers
        for provider_name, config in self.providers.items():
            self.usage_stats[provider_name] = {
                'requests': 0,
                'successes': 0,
                'failures': 0,
                'total_response_time': 0.0,
                'last_used': None,
                'consecutive_failures': 0,
                'flagged': False,
                'enabled': config.get('enabled', True)
            }
            
            # Initialize key rotation tracking
            self.provider_key_rotation[provider_name] = config.get('current_key_index', 0)
            self.consecutive_failures[provider_name] = config.get('consecutive_failures', 0)
            
            # Initialize enhanced per-key tracking
            api_keys = config.get('api_keys', [])
            valid_keys = [key for key in api_keys if key is not None]
            
            if valid_keys:
                self.key_usage_stats[provider_name] = {}
                self.key_last_used[provider_name] = {}
                self.key_request_count[provider_name] = {}
                
                for i, key in enumerate(api_keys):
                    if key is not None:
                        key_id = f"key_{i}"
                        self.key_usage_stats[provider_name][key_id] = {
                            'requests': 0,
                            'successes': 0,
                            'failures': 0,
                            'last_used': None,
                            'rate_limited': False,
                            'weight': 1.0,  # Load balancing weight
                            'requests_this_minute': 0
                        }
                        self.key_last_used[provider_name][key_id] = None
                        self.key_request_count[provider_name][key_id] = []
        
        if self.verbose:
            print(f"🚀 AI Engine v3.0 initialized with {len(self.providers)} providers")
            print(f"🔑 Key rotation: {'Enabled' if self.engine_settings.get('key_rotation_enabled', True) else 'Disabled'}")
            print(f"🔄 Provider rotation: {'Enabled' if self.engine_settings.get('provider_rotation_enabled', True) else 'Disabled'}")
            print(f"⚠️  Failure limit: {self.engine_settings.get('consecutive_failure_limit', 5)} consecutive failures")
    
    def _load_enabled_providers(self) -> Dict[str, Dict[str, Any]]:
        """Load only enabled providers with valid API keys from external config"""
        enabled_providers = {}
        
        for name, config in AI_CONFIGS.items():
            if config.get("enabled", True):
                # Check if provider needs API keys
                if config.get("auth_type") and config.get("api_keys"):
                    # Filter out None values from api_keys
                    valid_keys = [key for key in config["api_keys"] if key is not None]
                    if valid_keys:
                        config["api_keys"] = valid_keys
                        enabled_providers[name] = config
                    else:
                        self.logger.warning(f"Provider {name} disabled: No valid API keys found")
                elif not config.get("auth_type"):
                    # Provider doesn't need auth (like a3z, omegatron)
                    enabled_providers[name] = config
                else:
                    self.logger.warning(f"Provider {name} disabled: No API keys configured")
        
        self.logger.info(f"Loaded {len(enabled_providers)} enabled providers out of {len(AI_CONFIGS)} total")
        return enabled_providers
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('AI_engine')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _is_key_flagged(self, provider_name: str) -> bool:
        """Check if a provider's key is currently flagged"""
        if provider_name not in self.flagged_keys:
            return False
        
        flag_info = self.flagged_keys[provider_name]
        current_time = datetime.now()
        
        # Check if enough time has passed since flagging
        if current_time > flag_info['flag_until']:
            # Remove the flag
            del self.flagged_keys[provider_name]
            if self.verbose:
                print(f"🟢 {provider_name} key unflagged - retry available")
            return False
        
        return True
    
    def _get_current_api_key(self, provider_name: str) -> Optional[str]:
        """Get the optimal API key for a provider using intelligent load balancing"""
        config = self.providers.get(provider_name)
        if not config or not config.get('api_keys'):
            return None
            
        api_keys = config['api_keys']
        if not api_keys or all(key is None for key in api_keys):
            return None
            
        # Get the best available key using intelligent selection
        selected_index = self._select_optimal_key(provider_name)
        if selected_index is None:
            return None
            
        # Update tracking
        self.provider_key_rotation[provider_name] = selected_index
        self._track_key_usage(provider_name, selected_index)
        
        return api_keys[selected_index]
    
    def _select_optimal_key(self, provider_name: str) -> Optional[int]:
        """Select the optimal API key based on load balancing and rate limiting"""
        config = self.providers.get(provider_name)
        if not config or not config.get('api_keys'):
            return None
            
        api_keys = config['api_keys']
        valid_keys = [(i, key) for i, key in enumerate(api_keys) if key is not None]
        
        if not valid_keys:
            return None
            
        if len(valid_keys) == 1:
            return valid_keys[0][0]
        
        # Clean up old request counts (remove requests older than 1 minute)
        self._cleanup_request_counts(provider_name)
        
        current_time = datetime.now()
        best_key_index = None
        best_score = float('inf')
        
        for key_index, _ in valid_keys:
            key_id = f"key_{key_index}"
            
            # Skip if key is rate limited
            if provider_name in self.key_usage_stats:
                key_stats = self.key_usage_stats[provider_name].get(key_id, {})
                if key_stats.get('rate_limited', False):
                    # Check if rate limit cooldown has passed
                    last_used = key_stats.get('last_used')
                    if last_used and (current_time - last_used).total_seconds() < 60:
                        continue
                    else:
                        # Reset rate limit flag
                        key_stats['rate_limited'] = False
            
            # Calculate load score for this key
            score = self._calculate_key_load_score(provider_name, key_index)
            
            if score < best_score:
                best_score = score
                best_key_index = key_index
        
        if best_key_index is not None and self.verbose:
            print(f"🔑 Selected key #{best_key_index + 1} for {provider_name} (load score: {best_score:.2f})")
            
        return best_key_index
    
    def _calculate_key_load_score(self, provider_name: str, key_index: int) -> float:
        """Calculate load score for a key (lower = better)"""
        key_id = f"key_{key_index}"
        current_time = datetime.now()
        
        if provider_name not in self.key_usage_stats:
            return 0.0
            
        key_stats = self.key_usage_stats[provider_name].get(key_id, {})
        
        # Base score from recent usage
        requests_this_minute = len(self.key_request_count[provider_name].get(key_id, []))
        
        # Time since last use (encourage spreading load)
        last_used = key_stats.get('last_used')
        time_bonus = 0
        if last_used:
            seconds_since_use = (current_time - last_used).total_seconds()
            time_bonus = min(seconds_since_use / 60, 1.0)  # Max bonus of 1.0
        else:
            time_bonus = 1.0  # Unused key gets full bonus
        
        # Success rate factor
        total_requests = key_stats.get('requests', 0)
        successes = key_stats.get('successes', 0)
        if total_requests > 0:
            success_rate = successes / total_requests
            success_bonus = success_rate
        else:
            success_bonus = 1.0  # Unused key gets benefit of doubt
        
        # Weight factor from previous performance
        weight = key_stats.get('weight', 1.0)
        
        # Calculate final score (lower is better)
        load_score = (requests_this_minute * weight) - (time_bonus + success_bonus)
        
        return max(0, load_score)
    
    def _track_key_usage(self, provider_name: str, key_index: int):
        """Track usage of a specific key"""
        key_id = f"key_{key_index}"
        current_time = datetime.now()
        
        # Update request count tracking
        if provider_name in self.key_request_count:
            if key_id not in self.key_request_count[provider_name]:
                self.key_request_count[provider_name][key_id] = []
            self.key_request_count[provider_name][key_id].append(current_time)
        
        # Update usage stats
        if provider_name in self.key_usage_stats and key_id in self.key_usage_stats[provider_name]:
            self.key_usage_stats[provider_name][key_id]['requests'] += 1
            self.key_usage_stats[provider_name][key_id]['last_used'] = current_time
    
    def _cleanup_request_counts(self, provider_name: str):
        """Remove request timestamps older than 1 minute"""
        if provider_name not in self.key_request_count:
            return
            
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(minutes=1)
        
        for key_id in self.key_request_count[provider_name]:
            self.key_request_count[provider_name][key_id] = [
                timestamp for timestamp in self.key_request_count[provider_name][key_id]
                if timestamp > cutoff_time
            ]
    
    def _update_key_stats(self, provider_name: str, key_index: int, success: bool, response_time: float = 0):
        """Update statistics for a specific key"""
        key_id = f"key_{key_index}"
        
        if provider_name in self.key_usage_stats and key_id in self.key_usage_stats[provider_name]:
            key_stats = self.key_usage_stats[provider_name][key_id]
            
            if success:
                key_stats['successes'] += 1
                # Improve weight for successful keys
                key_stats['weight'] = max(0.5, key_stats['weight'] * 0.95)
                key_stats['rate_limited'] = False
            else:
                key_stats['failures'] += 1
                # Increase weight (penalty) for failing keys
                key_stats['weight'] = min(2.0, key_stats['weight'] * 1.1)
            
            key_stats['last_used'] = datetime.now()
    
    def _mark_key_rate_limited(self, provider_name: str, key_index: int):
        """Mark a specific key as rate limited"""
        key_id = f"key_{key_index}"
        
        if provider_name in self.key_usage_stats and key_id in self.key_usage_stats[provider_name]:
            self.key_usage_stats[provider_name][key_id]['rate_limited'] = True
            self.key_usage_stats[provider_name][key_id]['weight'] = 2.0  # Heavy penalty
            
            if self.verbose:
                print(f"🔴 Key #{key_index + 1} for {provider_name} marked as rate limited")
    
    def get_key_usage_report(self, provider_name: str) -> Dict:
        """Get detailed usage report for all keys of a provider"""
        if provider_name not in self.key_usage_stats:
            return {}
            
        report = {}
        config = self.providers.get(provider_name, {})
        api_keys = config.get('api_keys', [])
        
        for i, key in enumerate(api_keys):
            if key is not None:
                key_id = f"key_{i}"
                stats = self.key_usage_stats[provider_name].get(key_id, {})
                
                requests_this_minute = len(self.key_request_count[provider_name].get(key_id, []))
                
                report[f"Key #{i + 1}"] = {
                    'total_requests': stats.get('requests', 0),
                    'successes': stats.get('successes', 0),
                    'failures': stats.get('failures', 0),
                    'requests_this_minute': requests_this_minute,
                    'rate_limited': stats.get('rate_limited', False),
                    'weight': stats.get('weight', 1.0),
                    'last_used': stats.get('last_used'),
                    'success_rate': (stats.get('successes', 0) / max(1, stats.get('requests', 1))) * 100
                }
        
        return report
    
    def _rotate_api_key(self, provider_name: str) -> Optional[str]:
        """Intelligent API key rotation with load balancing"""
        if not self.engine_settings.get('key_rotation_enabled', True):
            return self._get_current_api_key(provider_name)
            
        config = self.providers.get(provider_name)
        if not config or not config.get('api_keys'):
            return None
            
        api_keys = config['api_keys']
        valid_keys = [key for key in api_keys if key is not None]
        
        if not valid_keys:
            return None
            
        if len(valid_keys) <= 1:
            # Only one key available, can't rotate
            return self._get_current_api_key(provider_name)
        
        # Mark current key as potentially problematic and select optimal one
        current_index = self.provider_key_rotation.get(provider_name, 0)
        self._mark_key_rate_limited(provider_name, current_index)
        
        # Get the best available key (excluding rate limited ones)
        selected_index = self._select_optimal_key(provider_name)
        
        if selected_index is not None:
            self.provider_key_rotation[provider_name] = selected_index
            if self.verbose:
                print(f"🔄 Intelligently rotated {provider_name} to key #{selected_index + 1}")
            return api_keys[selected_index]
            
        return None
    
    def _handle_provider_failure(self, provider_name: str, error_message: str, status_code: int = 0, response_json: dict = None):
        """
        Enhanced provider failure handling with smart error-based responses
        Triggers different actions based on the type of error detected
        """
        # Classify the error to determine appropriate response
        error_type = self._classify_error(error_message, status_code, response_json)
        
        # Increment consecutive failures
        self.consecutive_failures[provider_name] = self.consecutive_failures.get(provider_name, 0) + 1
        consecutive_count = self.consecutive_failures[provider_name]
        
        # Update usage stats
        if provider_name in self.usage_stats:
            self.usage_stats[provider_name]['failures'] += 1
            self.usage_stats[provider_name]['consecutive_failures'] = consecutive_count
        
        if self.verbose:
            print(f"🔍 {provider_name} error classified as: {error_type}")
        
        # Handle different error types with specific actions
        if error_type in ["rate_limit", "auth_error", "quota_exceeded"]:
            # These errors suggest key-level issues - try rotating API key immediately
            if self.engine_settings.get('key_rotation_enabled', True):
                rotated_key = self._rotate_api_key(provider_name)
                if rotated_key and self.verbose:
                    print(f"🔑 Rotated {provider_name} API key due to {error_type}")
                # Flag the specific key temporarily
                self._flag_key(provider_name, error_type)
            else:
                # If key rotation disabled, flag provider temporarily
                self._flag_provider(provider_name, duration_minutes=15)
                
        elif error_type in ["service_unavailable", "server_error", "network_error"]:
            # These errors suggest provider-level issues - flag provider temporarily
            self._flag_provider(provider_name, duration_minutes=10)
            if self.verbose:
                print(f"🚫 {provider_name} temporarily flagged due to {error_type}")
                
        # Check if we should flag the provider due to too many consecutive failures
        failure_limit = self.engine_settings.get('consecutive_failure_limit', 5)
        if consecutive_count >= failure_limit:
            self._flag_provider(provider_name, duration_minutes=30)
            if self.verbose:
                print(f"⚠️  {provider_name} flagged for 30min after {consecutive_count} consecutive failures")
        
        # Try key rotation for other types of failures after 2 attempts
        elif error_type == "unknown" and self.engine_settings.get('key_rotation_enabled', True) and consecutive_count >= 2:
            rotated_key = self._rotate_api_key(provider_name)
            if rotated_key and self.verbose:
                print(f"� Rotated {provider_name} API key after {consecutive_count} unknown failures")
    
    def _handle_provider_success(self, provider_name: str, response_time: float):
        """Handle successful provider response"""
        # Reset consecutive failures
        self.consecutive_failures[provider_name] = 0
        
        # Update usage stats
        if provider_name in self.usage_stats:
            stats = self.usage_stats[provider_name]
            stats['successes'] += 1
            stats['consecutive_failures'] = 0
            stats['last_used'] = datetime.now()
            stats['total_response_time'] += response_time
            
        # Unflag provider if it was flagged
        if provider_name in self.flagged_keys:
            del self.flagged_keys[provider_name]
            if self.verbose:
                print(f"🟢 {provider_name} unflagged after successful response")
    
    def _flag_provider(self, provider_name: str, duration_minutes: int = 30):
        """Flag a provider temporarily due to consecutive failures"""
        flag_until = datetime.now() + timedelta(minutes=duration_minutes)
        self.flagged_keys[provider_name] = {
            'flagged_at': datetime.now(),
            'flag_until': flag_until,
            'reason': 'consecutive_failures'
        }
        
        # Mark provider as flagged in usage stats
        if provider_name in self.usage_stats:
            self.usage_stats[provider_name]['flagged'] = True
    
    def _flag_key(self, provider_name: str, error_type: str = "unknown"):
        """Flag a provider's key based on error type"""
        current_time = datetime.now()
        
        if error_type in ["rate_limit", "auth_error"]:
            # Flag for 1 hour for rate limits and auth errors
            flag_until = current_time + timedelta(hours=1)
        elif error_type == "daily_limit":
            # Flag until midnight for daily limits
            tomorrow = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            flag_until = tomorrow
        else:
            # Default: flag for 30 minutes
            flag_until = current_time + timedelta(minutes=30)
        
        self.flagged_keys[provider_name] = {
            'flagged_at': current_time,
            'flag_until': flag_until,
            'error_type': error_type,
            'consecutive_failures': self.usage_stats[provider_name]['consecutive_failures']
        }
        
        if self.verbose:
            duration = (flag_until - current_time).total_seconds() / 60
            print(f"🔴 {provider_name} key flagged for {duration:.0f} minutes due to {error_type}")
    
    def _classify_error(self, error_message: str, status_code: int, response_json: dict = None) -> str:
        """
        Enhanced error classification based on actual server responses
        Detects specific error types from API responses to trigger appropriate actions
        """
        error_lower = error_message.lower()
        
        # Parse JSON response for specific error details
        error_details = ""
        if response_json and isinstance(response_json, dict):
            error_details = str(response_json).lower()
            
        combined_text = f"{error_lower} {error_details}"
        
        # Rate limiting detection (triggers key rotation)
        rate_limit_patterns = [
            "rate limit", "too many requests", "quota exceeded", "requests per minute",
            "rpm exceeded", "rate limited", "throttled", "429", "rate_limit_exceeded",
            "requests_per_minute_limit_exceeded", "rate_limit_reached"
        ]
        if any(pattern in combined_text for pattern in rate_limit_patterns) or status_code == 429:
            return "rate_limit"
        
        # Authentication errors (triggers key rotation)  
        auth_error_patterns = [
            "invalid key", "unauthorized", "forbidden", "api key", "invalid_api_key",
            "authentication failed", "invalid token", "access denied", "invalid_request_error",
            "incorrect api key", "invalid_api_key", "api_key_invalid", "authentication_error"
        ]
        if any(pattern in combined_text for pattern in auth_error_patterns) or status_code in [401, 403]:
            return "auth_error"
        
        # Quota/limit errors (triggers key rotation or provider flagging)
        quota_patterns = [
            "daily limit", "monthly quota", "usage limit", "quota_exceeded", "insufficient_quota",
            "billing_hard_limit_reached", "usage_limit_exceeded", "credit limit", "balance insufficient"
        ]
        if any(pattern in combined_text for pattern in quota_patterns):
            return "quota_exceeded"
        
        # Model/service unavailable (triggers provider rotation)
        service_patterns = [
            "model not found", "service unavailable", "model_not_found", "invalid_model",
            "model temporarily unavailable", "service_unavailable", "model_overloaded",
            "engine_overloaded", "server_overloaded"
        ]
        if any(pattern in combined_text for pattern in service_patterns) or status_code == 503:
            return "service_unavailable"
        
        # Server errors (triggers provider rotation)
        if 500 <= status_code < 600:
            return "server_error"
        
        # Network/timeout errors (triggers provider rotation)
        network_patterns = [
            "timeout", "connection error", "network error", "connection timeout",
            "read timeout", "connect timeout", "connection refused", "network_error"
        ]
        if any(pattern in combined_text for pattern in network_patterns):
            return "network_error"
        
        # Bad request (may need different handling)
        if status_code == 400:
            return "bad_request"
            
        return "unknown"
    
    def _get_available_providers(self) -> List[Tuple[str, Dict]]:
        """Get list of available providers sorted by priority"""
        available = []
        
        for name, config in self.providers.items():
            if not self._is_key_flagged(name):
                available.append((name, config))
        
        # Sort by priority (lower number = higher priority)
        available.sort(key=lambda x: x[1]['priority'])
        return available
    
    def _update_stats(self, provider_name: str, success: bool, response_time: float):
        """Update usage statistics for a provider and current key"""
        stats = self.usage_stats[provider_name]
        stats['requests'] += 1
        stats['last_used'] = datetime.now()
        stats['total_response_time'] += response_time
        
        # Update key-specific stats
        current_key_index = self.provider_key_rotation.get(provider_name, 0)
        self._update_key_stats(provider_name, current_key_index, success, response_time)
        
        if success:
            stats['successes'] += 1
            stats['consecutive_failures'] = 0
        else:
            stats['failures'] += 1
            stats['consecutive_failures'] += 1
            
            # Auto-flag after 5 consecutive failures
            if stats['consecutive_failures'] >= 5:
                self._flag_key(provider_name, "consecutive_failures")
    
    def chat_completion(self, messages: List[Dict[str, str]], model: str = None, **kwargs) -> RequestResult:
        """
        Main chat completion method with smart provider rotation
        """
        available_providers = self._get_available_providers()
        
        if not available_providers:
            return RequestResult(
                success=False,
                error_message="No available providers",
                error_type="no_providers"
            )
        
        # Try each available provider
        for provider_name, provider_config in available_providers:
            start_time = time.time()
            
            try:
                if self.verbose:
                    print(f"🔄 Trying {provider_name}...")
                
                result = self._make_request(provider_name, provider_config, messages, model, **kwargs)
                response_time = time.time() - start_time
                
                self._update_stats(provider_name, result.success, response_time)
                
                if result.success:
                    result.provider_used = provider_name
                    result.response_time = response_time
                    self.current_provider = provider_name
                    
                    # Handle successful response with advanced tracking
                    self._handle_provider_success(provider_name, response_time)
                    
                    if self.verbose:
                        print(f"✅ {provider_name} successful ({response_time:.2f}s)")
                    
                    return result
                else:
                    # Handle failure with enhanced error detection and smart rotation
                    self._handle_provider_failure(
                        provider_name, 
                        result.error_message, 
                        result.status_code, 
                        result.raw_response
                    )
                    
                    if self.verbose:
                        print(f"❌ {provider_name} failed: {result.error_message}")
                    
                    # Continue to next provider (automatic provider rotation)
                    continue
                    
            except Exception as e:
                response_time = time.time() - start_time
                self._update_stats(provider_name, False, response_time)
                
                # Handle exception as failure with enhanced tracking
                self._handle_provider_failure(provider_name, str(e), 0, None)
                
                if self.verbose:
                    print(f"💥 {provider_name} exception: {str(e)}")
                
                # Continue to next provider (automatic provider rotation)
                continue
        
        # All providers failed
        return RequestResult(
            success=False,
            error_message="All providers failed",
            error_type="all_failed"
        )
    
    def _make_request(self, provider_name: str, config: Dict, messages: List[Dict], model: str = None, **kwargs) -> RequestResult:
        """Make a request to a specific provider"""
        try:
            format_type = config.get('format', 'openai')
            
            if format_type == 'openai':
                return self._make_openai_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'gemini':
                return self._make_gemini_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'cohere':
                return self._make_cohere_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'a3z_get':
                return self._make_a3z_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'cloudflare':
                return self._make_cloudflare_request(provider_name, config, messages, model, **kwargs)
            else:
                return RequestResult(
                    success=False,
                    error_message=f"Unsupported format: {format_type}",
                    error_type="unsupported_format"
                )
                
        except Exception as e:
            return RequestResult(
                success=False,
                error_message=str(e),
                error_type="request_exception"
            )
    
    def _make_openai_request(self, provider_name: str, config: Dict, messages: List[Dict], model: str = None, **kwargs) -> RequestResult:
        """Make OpenAI-compatible request"""
        url = config['endpoint']
        headers = {'Content-Type': 'application/json'}
        
        # Add authentication
        if config.get('auth_type') == 'bearer':
            api_key = self._get_current_api_key(provider_name)
            if api_key:
                headers['Authorization'] = f"Bearer {api_key}"
        
        # Special handling for providers requiring multiple messages (like Pawan)
        if provider_name == 'pawan' and len(messages) == 1:
            # Add a system message to meet the 2-message requirement
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant."},
                messages[0]
            ]
        
        # Prepare data
        data = {
            'model': model or config['model'],
            'messages': messages
        }
        
        # Add optional parameters
        if config.get('max_tokens'):
            data['max_tokens'] = config['max_tokens']
        if config.get('temperature') is not None:
            data['temperature'] = config['temperature']
        
        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=config.get('timeout', 60)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # Validate that we actually got content
                if not content or content.strip() == '':
                    return RequestResult(
                        success=False,
                        error_message=f"Empty response from {provider_name}",
                        status_code=response.status_code,
                        error_type="empty_response",
                        raw_response=response_data
                    )
                
                return RequestResult(
                    success=True,
                    content=content,
                    status_code=response.status_code,
                    raw_response=response_data
                )
            else:
                # Try to parse JSON error response for better error classification
                try:
                    error_json = response.json()
                except:
                    error_json = None
                    
                return RequestResult(
                    success=False,
                    error_message=response.text,
                    status_code=response.status_code,
                    error_type="http_error",
                    raw_response=error_json
                )
                
        except requests.exceptions.Timeout:
            return RequestResult(
                success=False,
                error_message="Request timeout",
                error_type="timeout"
            )
        except Exception as e:
            return RequestResult(
                success=False,
                error_message=str(e),
                error_type="request_exception"
            )
    
    def _make_gemini_request(self, provider_name: str, config: Dict, messages: List[Dict], model: str = None, **kwargs) -> RequestResult:
        """Make Gemini API request"""
        url = config['endpoint']
        api_key = self._get_current_api_key(provider_name)
        if api_key:
            url += f"?key={api_key}"
        
        # Convert messages to Gemini format
        parts = []
        for msg in messages:
            if msg['role'] == 'user':
                parts.append({"text": msg['content']})
        
        data = {
            "contents": [{
                "parts": parts
            }]
        }
        
        try:
            response = requests.post(
                url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=config.get('timeout', 60)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                content = response_data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                
                return RequestResult(
                    success=True,
                    content=content,
                    status_code=response.status_code,
                    raw_response=response_data
                )
            else:
                return RequestResult(
                    success=False,
                    error_message=response.text,
                    status_code=response.status_code,
                    error_type="http_error"
                )
                
        except Exception as e:
            return RequestResult(
                success=False,
                error_message=str(e),
                error_type="request_exception"
            )
    
    def _make_cohere_request(self, provider_name: str, config: Dict, messages: List[Dict], model: str = None, **kwargs) -> RequestResult:
        """Make Cohere API request"""
        url = config['endpoint']
        headers = {'Content-Type': 'application/json'}
        
        api_key = self._get_current_api_key(provider_name)
        if api_key:
            headers['authorization'] = f"bearer {api_key}"
        
        # Convert to Cohere v2 format - uses messages array directly
        data = {
            "model": model or config['model'],
            "messages": messages
        }
        
        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=config.get('timeout', 60)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                # Cohere v2 response format
                content = response_data.get('message', {}).get('content', [{}])[0].get('text', '')
                
                # Validate that we actually got content
                if not content or content.strip() == '':
                    return RequestResult(
                        success=False,
                        error_message="Empty response from Cohere",
                        status_code=response.status_code,
                        error_type="empty_response",
                        raw_response=response_data
                    )
                
                return RequestResult(
                    success=True,
                    content=content,
                    status_code=response.status_code,
                    raw_response=response_data
                )
            else:
                return RequestResult(
                    success=False,
                    error_message=response.text,
                    status_code=response.status_code,
                    error_type="http_error"
                )
                
        except Exception as e:
            return RequestResult(
                success=False,
                error_message=str(e),
                error_type="request_exception"
            )
    
    def _make_a3z_request(self, provider_name: str, config: Dict, messages: List[Dict], model: str = None, **kwargs) -> RequestResult:
        """Make A3Z GET request"""
        url = config['endpoint']
        user_message = messages[-1]['content'] if messages else ""
        
        # A3Z format: user parameter + model
        params = {
            'user': user_message,
            'model': model or config['model']
        }
        
        try:
            response = requests.get(
                url,
                params=params,
                timeout=config.get('timeout', 60)
            )
            
            if response.status_code == 200:
                # A3Z returns JSON in OpenAI format, need to parse it
                try:
                    response_data = response.json()
                    content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                except (ValueError, KeyError, IndexError):
                    # Fallback to raw text if JSON parsing fails
                    content = response.text
                
                # Validate that we actually got content
                if not content or content.strip() == '':
                    return RequestResult(
                        success=False,
                        error_message="Empty response from A3Z",
                        status_code=response.status_code,
                        error_type="empty_response"
                    )
                
                return RequestResult(
                    success=True,
                    content=content,
                    status_code=response.status_code,
                    raw_response=response_data if 'response_data' in locals() else response.text
                )
            else:
                return RequestResult(
                    success=False,
                    error_message=response.text,
                    status_code=response.status_code,
                    error_type="http_error"
                )
                
        except Exception as e:
            return RequestResult(
                success=False,
                error_message=str(e),
                error_type="request_exception"
            )
    
    def _make_cloudflare_request(self, provider_name: str, config: Dict, messages: List[Dict], model: str = None, **kwargs) -> RequestResult:
        """Make Cloudflare API request"""
        if not config.get('account_id'):
            return RequestResult(
                success=False,
                error_message="Cloudflare account_id not configured",
                error_type="config_error"
            )
        
        # Cloudflare Workers AI - model is in URL path
        url = config['endpoint'].format(account_id=config['account_id'])
        headers = {'Content-Type': 'application/json'}
        
        api_key = self._get_current_api_key(provider_name)
        if api_key:
            headers['Authorization'] = f"Bearer {api_key}"
        
        # Cloudflare Workers AI format - chat completions endpoint uses OpenAI format
        data = {
            'model': model or config['model'],
            'messages': messages
        }
        
        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=config.get('timeout', 60)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                # Cloudflare chat completions response format (standard OpenAI-compatible)
                content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # Validate that we actually got content
                if not content or content.strip() == '':
                    return RequestResult(
                        success=False,
                        error_message="Empty response from Cloudflare",
                        status_code=response.status_code,
                        error_type="empty_response",
                        raw_response=response_data
                    )
                
                return RequestResult(
                    success=True,
                    content=content,
                    status_code=response.status_code,
                    raw_response=response_data
                )
            else:
                return RequestResult(
                    success=False,
                    error_message=response.text,
                    status_code=response.status_code,
                    error_type="http_error"
                )
                
        except Exception as e:
            return RequestResult(
                success=False,
                error_message=str(e),
                error_type="request_exception"
            )
    
    def stress_test_providers(self, test_iterations: int = 3, ask_for_priority_change: bool = True) -> Dict[str, Any]:
        """
        Run stress test on all providers and optionally ask user for priority changes
        """
        print(f"🧪 Starting stress test on {len(self.providers)} providers...")
        print(f"📝 Test iterations: {test_iterations}")
        print()
        
        test_prompt = "Hello! Please respond with exactly: 'Test successful - AI Engine v3.0 working!'"
        results = {}
        
        for provider_name, provider_config in self.providers.items():
            print(f"Testing {provider_name}...", end=" ")
            
            provider_results = {
                'provider': provider_name,
                'total_tests': test_iterations,
                'successful_tests': 0,
                'failed_tests': 0,
                'response_times': [],
                'errors': []
            }
            
            for i in range(test_iterations):
                start_time = time.time()
                result = self._make_request(
                    provider_name, 
                    provider_config, 
                    [{"role": "user", "content": test_prompt}]
                )
                response_time = time.time() - start_time
                
                if result.success:
                    provider_results['successful_tests'] += 1
                    provider_results['response_times'].append(response_time)
                else:
                    provider_results['failed_tests'] += 1
                    provider_results['errors'].append({
                        'iteration': i + 1,
                        'error': result.error_message,
                        'error_type': result.error_type
                    })
            
            # Calculate metrics
            success_rate = (provider_results['successful_tests'] / test_iterations) * 100
            avg_response_time = sum(provider_results['response_times']) / len(provider_results['response_times']) if provider_results['response_times'] else 0
            
            provider_results.update({
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'min_response_time': min(provider_results['response_times']) if provider_results['response_times'] else 0,
                'max_response_time': max(provider_results['response_times']) if provider_results['response_times'] else 0,
                'passed': success_rate >= 75  # 75% success threshold
            })
            
            results[provider_name] = provider_results
            
            status = "✅ PASS" if provider_results['passed'] else "❌ FAIL"
            print(f"{status} ({success_rate:.1f}%, {avg_response_time:.2f}s)")
        
        # Calculate overall stats
        total_providers = len(results)
        passed_providers = sum(1 for r in results.values() if r['passed'])
        pass_rate = (passed_providers / total_providers) * 100
        
        print(f"\n📊 STRESS TEST SUMMARY:")
        print(f"Providers tested: {total_providers}")
        print(f"Providers passed: {passed_providers}")
        print(f"Overall pass rate: {pass_rate:.1f}%")
        
        # Ask user about priority changes if requested
        if ask_for_priority_change and passed_providers > 0:
            print(f"\n🔄 Priority Optimization Available")
            print(f"Would you like to optimize provider priorities based on test results?")
            
            response = input("Enter 'y' to optimize priorities or 'n' to keep current: ").lower().strip()
            
            if response == 'y':
                self._optimize_priorities(results)
                print("✅ Provider priorities optimized!")
            else:
                print("📌 Keeping current priorities")
        
        return results
    
    def _optimize_priorities(self, test_results: Dict[str, Any]):
        """Optimize provider priorities based on test results"""
        # Sort providers by performance score
        provider_scores = []
        
        for provider_name, result in test_results.items():
            if result['passed']:
                # Calculate performance score (success rate 60%, speed 40%)
                success_weight = result['success_rate'] * 0.6
                speed_score = max(0, 100 - (result['avg_response_time'] * 20))  # Penalize slow responses
                speed_weight = speed_score * 0.4
                
                total_score = success_weight + speed_weight
                provider_scores.append((provider_name, total_score, result['avg_response_time']))
        
        # Sort by score (higher is better)
        provider_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Update priorities
        for i, (provider_name, score, avg_time) in enumerate(provider_scores, 1):
            self.providers[provider_name]['priority'] = i
            print(f"  {i:2d}. {provider_name:15} (Score: {score:5.1f}, Time: {avg_time:.2f}s)")
    
    def test_specific_provider(self, provider_name: str, test_message: str = None) -> RequestResult:
        """
        Test a specific provider directly, bypassing priority selection
        """
        if provider_name not in self.providers:
            return RequestResult(
                success=False,
                error_message=f"Provider '{provider_name}' not found. Available providers: {', '.join(self.providers.keys())}",
                error_type="provider_not_found"
            )
        
        provider_config = self.providers[provider_name]
        
        # Check if provider is flagged
        if self._is_key_flagged(provider_name):
            flag_info = self.flagged_keys[provider_name]
            return RequestResult(
                success=False,
                error_message=f"Provider '{provider_name}' is currently flagged due to {flag_info['error_type']}. Retry available at {flag_info['flag_until'].strftime('%H:%M:%S')}",
                error_type="provider_flagged"
            )
        
        # Use default test message if none provided
        if not test_message:
            test_message = f"Hello! Please respond with: '{provider_name} test successful!'"
        
        messages = [{"role": "user", "content": test_message}]
        
        # Test the specific provider
        start_time = time.time()
        
        try:
            if self.verbose:
                print(f"🧪 Testing {provider_name} specifically...")
            
            result = self._make_request(provider_name, provider_config, messages)
            response_time = time.time() - start_time
            
            # Update stats
            self._update_stats(provider_name, result.success, response_time)
            
            if result.success:
                result.provider_used = provider_name
                result.response_time = response_time
                
                if self.verbose:
                    print(f"✅ {provider_name} test successful ({response_time:.2f}s)")
            else:
                # Handle errors and flagging
                error_type = self._classify_error(result.error_message, result.status_code)
                
                if error_type in ["rate_limit", "daily_limit", "auth_error"]:
                    self._flag_key(provider_name, error_type)
                
                if self.verbose:
                    print(f"❌ {provider_name} test failed: {result.error_message}")
            
            return result
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(provider_name, False, response_time)
            
            if self.verbose:
                print(f"💥 {provider_name} exception: {str(e)}")
            
            return RequestResult(
                success=False,
                error_message=str(e),
                error_type="request_exception",
                response_time=response_time
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current engine status"""
        available_providers = self._get_available_providers()
        flagged_count = len(self.flagged_keys)
        
        status = {
            'total_providers': len(self.providers),
            'available_providers': len(available_providers),
            'flagged_providers': flagged_count,
            'current_provider': self.current_provider,
            'available_provider_list': [p[0] for p in available_providers[:5]],  # Top 5
            'flagged_provider_list': list(self.flagged_keys.keys())
        }
        
        return status

# Test function
def main():
    """Test the AI Engine with command-line support"""
    import sys
    
    # Check for command-line arguments
    if len(sys.argv) > 1:
        provider_name = sys.argv[1].lower()
        
        # Handle special commands
        if provider_name == "stress":
            engine = AI_engine(verbose=True)
            print("🧪 Running comprehensive stress test...")
            results = engine.stress_test_providers(test_iterations=3, ask_for_priority_change=True)
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
            # Show key usage statistics
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
            # Auto mode - use priority-based provider rotation
            engine = AI_engine(verbose=True)
            
            custom_message = "Hello! Please respond with a short test message to verify the system is working."
            if len(sys.argv) > 2:
                custom_message = " ".join(sys.argv[2:])
            
            print(f"🔄 Testing automatic provider rotation...")
            print("-" * 50)
            
            messages = [{"role": "user", "content": custom_message}]
            result = engine.chat_completion(messages)
            
            if result.success:
                print(f"✅ AUTO ROTATION SUCCESS!")
                print(f"💬 Response: {result.content}")
                print(f"🏃‍♂️ Provider used: {result.provider_used}")
                print(f"⏱️ Response time: {result.response_time:.2f}s")
            else:
                print(f"❌ AUTO ROTATION FAILED!")
                print(f"🚨 Error: {result.error_message}")
                print(f"🔍 Error type: {result.error_type}")
            return
        
        # Test specific provider
        engine = AI_engine(verbose=True)
        
        # Custom message if provided
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
    
    # Show status
    status = engine.get_status()
    print(f"\n📊 Engine Status:")
    print(f"Available providers: {status['available_providers']}/{status['total_providers']}")
    print(f"Top providers: {', '.join(status['available_provider_list'])}")
    
    # Show usage help
    print(f"\n💡 Usage:")
    print(f"  python ai_engine.py                    # Test with priority selection")
    print(f"  python ai_engine.py <provider>         # Test specific provider")
    print(f"  python ai_engine.py <provider> <msg>   # Test with custom message")
    print(f"  python ai_engine.py list               # List all providers")
    print(f"  python ai_engine.py status             # Show engine status")
    print(f"  python ai_engine.py keys               # Show key usage for all providers")
    print(f"  python ai_engine.py keys <provider>    # Show detailed key usage for provider")
    print(f"  python ai_engine.py stress             # Run stress test")

if __name__ == "__main__":
    main()
