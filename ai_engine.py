import os
import time
import asyncio
import aiohttp
import requests
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import random
import logging
import concurrent.futures
import threading
from dotenv import load_dotenv
from dataclasses import dataclass

# Import configuration from external config file
try:
    from config import AI_CONFIGS, ENGINE_SETTINGS, AUTODECIDE_CONFIG, verbose_print
    from model_cache import shared_model_cache
except ImportError as e:
    print(f"Failed to import from config: {e}")
    print("Falling back to inline configuration...")
    AI_CONFIGS = {}
    ENGINE_SETTINGS = {"key_rotation_enabled": True, "provider_rotation_enabled": True, "consecutive_failure_limit": 5, "verbose_mode": False}
    AUTODECIDE_CONFIG = {"enabled": True, "cache_duration": 1800, "model_cache": {}}
    
    # Fallback verbose_print function
    def verbose_print(message: str, verbose_override: bool = None):
        if verbose_override or ENGINE_SETTINGS.get("verbose_mode", False):
            print(message)

# Import Statistics Manager
try:
    from statistics_manager import StatisticsManager, get_stats_manager, save_statistics_now
except ImportError as e:
    print(f"Failed to import StatisticsManager: {e}")
    print("Statistics persistence will be disabled")
    StatisticsManager = None
    get_stats_manager = lambda: None
    save_statistics_now = lambda: None

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
    model_used: str = ""
    raw_response: Optional[Dict] = None

class AI_engine:
    """
    Clean AI Engine v3.0 with Python-based configuration and smart key rotation
    """
    
    def __init__(self, verbose: bool = None):
        """Initialize the AI Engine v3.0 with external configuration and advanced features"""
        # Set verbose mode: instance override > global config > default False
        if verbose is not None:
            self.verbose = verbose
        else:
            self.verbose = ENGINE_SETTINGS.get("verbose_mode", False)
            
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
        
        # Initialize Statistics Manager
        self.stats_manager = get_stats_manager()
        
        # Initialize Autodecide feature - use shared cache
        self.autodecide_config = AUTODECIDE_CONFIG
        
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
            
            # Initialize enhanced per-key tracking with persistent data from StatisticsManager
            api_keys = config.get('api_keys', [])
            valid_keys = [key for key in api_keys if key is not None]
            
            if valid_keys:
                self.key_usage_stats[provider_name] = {}
                self.key_last_used[provider_name] = {}
                self.key_request_count[provider_name] = {}
                
                for i, key in enumerate(api_keys):
                    if key is not None:
                        key_id = f"key_{i}"
                        
                        # Load persistent statistics for this key from StatisticsManager
                        persistent_key_stats = self.stats_manager.get_statistics(provider_name, key_id)
                        
                        if persistent_key_stats:
                            # Use persistent data
                            self.key_usage_stats[provider_name][key_id] = {
                                'requests': persistent_key_stats.requests,
                                'successes': persistent_key_stats.successes,
                                'failures': persistent_key_stats.failures,
                                'last_used': persistent_key_stats.last_used,
                                'rate_limited': persistent_key_stats.rate_limited,
                                'weight': persistent_key_stats.weight,
                                'requests_this_minute': 0
                            }
                            self.key_last_used[provider_name][key_id] = persistent_key_stats.last_used
                        else:
                            # Initialize with defaults
                            self.key_usage_stats[provider_name][key_id] = {
                                'requests': 0,
                                'successes': 0,
                                'failures': 0,
                                'last_used': None,
                                'rate_limited': False,
                                'weight': 1.0,
                                'requests_this_minute': 0
                            }
                            self.key_last_used[provider_name][key_id] = None
                        
                        self.key_request_count[provider_name][key_id] = []
        
        if self.verbose:
            verbose_print(f"🚀 AI Engine v3.0 initialized with {len(self.providers)} providers", self.verbose)
            verbose_print(f"🔑 Key rotation: {'Enabled' if self.engine_settings.get('key_rotation_enabled', True) else 'Disabled'}", self.verbose)
            verbose_print(f"🔄 Provider rotation: {'Enabled' if self.engine_settings.get('provider_rotation_enabled', True) else 'Disabled'}", self.verbose)
            verbose_print(f"⚠️  Failure limit: {self.engine_settings.get('consecutive_failure_limit', 5)} consecutive failures", self.verbose)
            verbose_print(f"💾 Persistent statistics: {'Loaded' if self.stats_manager.get_stats_summary()['total_providers'] > 0 else 'None found'}", self.verbose)
    
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
                        if self.verbose:
                            verbose_print(f"Provider {name} disabled: No valid API keys found", self.verbose)
                elif not config.get("auth_type"):
                    # Provider doesn't need auth (like a3z, omegatron)
                    enabled_providers[name] = config
                else:
                    if self.verbose:
                        verbose_print(f"Provider {name} disabled: No API keys configured", self.verbose)
        
        if self.verbose:
            verbose_print(f"Loaded {len(enabled_providers)} enabled providers out of {len(AI_CONFIGS)} total", self.verbose)
        return enabled_providers
    
    def set_verbose(self, verbose: bool):
        """
        Set verbose mode for this AI_engine instance
        
        Args:
            verbose (bool): Enable or disable verbose output
        """
        self.verbose = verbose
        verbose_print(f"🔧 AI Engine verbose mode: {'Enabled' if verbose else 'Disabled'}", self.verbose)
    
    def get_verbose(self) -> bool:
        """
        Get current verbose mode setting
        
        Returns:
            bool: Current verbose mode state
        """
        return self.verbose
    
    def set_global_verbose(self, verbose: bool):
        """
        Set global verbose mode in ENGINE_SETTINGS (affects all new instances)
        
        Args:
            verbose (bool): Enable or disable global verbose output
        """
        ENGINE_SETTINGS["verbose_mode"] = verbose
        verbose_print(f"🌍 Global verbose mode: {'Enabled' if verbose else 'Disabled'}", verbose)
    
    def get_global_verbose(self) -> bool:
        """
        Get global verbose mode setting
        
        Returns:
            bool: Global verbose mode state
        """
        return ENGINE_SETTINGS.get("verbose_mode", False)
    
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
                verbose_print(f"🟢 {provider_name} key unflagged - retry available", self.verbose)
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
            verbose_print(f"🔑 Selected key #{best_key_index + 1} for {provider_name} (load score: {best_score:.2f})", self.verbose)
            
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
        """Track usage of a specific key and update persistent storage"""
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
            
            # Update StatisticsManager (this handles persistence automatically)
            # Note: We don't update success/failure here, that's done in _update_key_stats
    
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
        """Update statistics for a specific key in both memory and persistent storage"""
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
            
            # Update StatisticsManager with the results
            self.stats_manager.update_statistics(provider_name, key_id, success, response_time)
    
    def _mark_key_rate_limited(self, provider_name: str, key_index: int):
        """Mark a specific key as rate limited and update persistent storage"""
        key_id = f"key_{key_index}"
        
        if provider_name in self.key_usage_stats and key_id in self.key_usage_stats[provider_name]:
            self.key_usage_stats[provider_name][key_id]['rate_limited'] = True
            self.key_usage_stats[provider_name][key_id]['weight'] = 2.0  # Heavy penalty
            
            # Update StatisticsManager
            self.stats_manager.mark_rate_limited(provider_name, key_id)
            
            if self.verbose:
                verbose_print(f"🔴 Key #{key_index + 1} for {provider_name} marked as rate limited", self.verbose)
    
    def get_key_usage_report(self, provider_name: str) -> Dict:
        """Get detailed usage report for all keys of a provider using persistent statistics"""
        if provider_name not in self.providers:
            return {}
            
        report = {}
        config = self.providers.get(provider_name, {})
        api_keys = config.get('api_keys', [])
        
        for i, key in enumerate(api_keys):
            if key is not None:
                key_id = f"key_{i}"
                
                # Get statistics from StatisticsManager
                persistent_stats = self.stats_manager.get_statistics(provider_name, key_id)
                memory_stats = self.key_usage_stats.get(provider_name, {}).get(key_id, {})
                
                if persistent_stats:
                    # Use persistent data as base, merge with memory data
                    stats = {
                        'total_requests': persistent_stats.requests,
                        'successes': persistent_stats.successes,
                        'failures': persistent_stats.failures,
                        'rate_limited': persistent_stats.rate_limited,
                        'weight': persistent_stats.weight,
                        'last_used': persistent_stats.last_used
                    }
                    # Merge memory stats (these take precedence for current session)
                    stats.update(memory_stats)
                else:
                    # Fall back to memory stats only
                    stats = memory_stats.copy()
                
                requests_this_minute = len(self.key_request_count.get(provider_name, {}).get(key_id, []))
                
                report[f"Key #{i + 1}"] = {
                    'total_requests': stats.get('total_requests', stats.get('requests', 0)),
                    'successes': stats.get('successes', 0),
                    'failures': stats.get('failures', 0),
                    'requests_this_minute': requests_this_minute,
                    'rate_limited': stats.get('rate_limited', False),
                    'weight': stats.get('weight', 1.0),
                    'last_used': stats.get('last_used'),
                    'success_rate': (stats.get('successes', 0) / max(1, stats.get('total_requests', stats.get('requests', 1)))) * 100
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
                verbose_print(f"🔄 Intelligently rotated {provider_name} to key #{selected_index + 1}", self.verbose)
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
            self.usage_stats[provider_name]['last_failure'] = datetime.now()
        
        if self.verbose:
            verbose_print(f"🔍 {provider_name} error classified as: {error_type}", self.verbose)
        
        # Handle different error types with specific actions
        if error_type in ["rate_limit", "auth_error", "quota_exceeded"]:
            # These errors suggest key-level issues - try rotating API key immediately
            if self.engine_settings.get('key_rotation_enabled', True):
                rotated_key = self._rotate_api_key(provider_name)
                if rotated_key and self.verbose:
                    verbose_print(f"🔑 Rotated {provider_name} API key due to {error_type}", self.verbose)
                # Flag the specific key temporarily
                self._flag_key(provider_name, error_type)
            else:
                # If key rotation disabled, flag provider temporarily
                self._flag_provider(provider_name, duration_minutes=15)
                
        elif error_type in ["service_unavailable", "server_error", "network_error"]:
            # These errors suggest provider-level issues - flag provider temporarily
            self._flag_provider(provider_name, duration_minutes=10)
            if self.verbose:
                verbose_print(f"🚫 {provider_name} temporarily flagged due to {error_type}", self.verbose)
                
        # Check if we should flag the provider due to too many consecutive failures
        failure_limit = self.engine_settings.get('consecutive_failure_limit', 5)
        if consecutive_count >= failure_limit:
            self._flag_provider(provider_name, duration_minutes=30)
            if self.verbose:
                verbose_print(f"⚠️  {provider_name} flagged for 30min after {consecutive_count} consecutive failures", self.verbose)
        
        # Try key rotation for other types of failures after 2 attempts
        elif error_type == "unknown" and self.engine_settings.get('key_rotation_enabled', True) and consecutive_count >= 2:
            rotated_key = self._rotate_api_key(provider_name)
            if rotated_key and self.verbose:
                verbose_print(f"� Rotated {provider_name} API key after {consecutive_count} unknown failures", self.verbose)
    
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
            stats['last_success'] = datetime.now()
            stats['total_response_time'] += response_time
            
        # Unflag provider if it was flagged
        if provider_name in self.flagged_keys:
            del self.flagged_keys[provider_name]
            if self.verbose:
                verbose_print(f"🟢 {provider_name} unflagged after successful response", self.verbose)
        
        # Reset any rate-limited keys for this provider since it's working
        self._reset_rate_limited_keys(provider_name)

    def _reset_rate_limited_keys(self, provider_name: str):
        """Reset rate limited status for provider keys after successful request"""
        if provider_name in self.key_usage_stats:
            reset_count = 0
            for key_id, stats in self.key_usage_stats[provider_name].items():
                if stats.get('rate_limited', False):
                    stats['rate_limited'] = False
                    reset_count += 1
            
            if reset_count > 0 and self.verbose:
                verbose_print(f"🔄 Reset rate limit status for {reset_count} keys in {provider_name}", self.verbose)

    def _check_provider_recovery(self, provider_name: str) -> bool:
        """
        Check if a provider has likely recovered from previous issues
        Returns True if provider should be tried again
        """
        if provider_name not in self.usage_stats:
            return True  # No history, worth trying
        
        stats = self.usage_stats[provider_name]
        current_time = datetime.now()
        
        # If provider was flagged, check if flag has expired
        if self._is_key_flagged(provider_name):
            return False
        
        # Check if enough time has passed since last failure
        last_failure = stats.get('last_failure')
        if last_failure:
            time_since_failure = current_time - last_failure
            # Recovery time increases with consecutive failures
            recovery_minutes = min(stats.get('consecutive_failures', 0) * 2, 30)
            
            if time_since_failure.total_seconds() < recovery_minutes * 60:
                return False
        
        # Check success rate - if it's too low recently, wait longer
        recent_requests = stats.get('requests', 0)
        recent_successes = stats.get('successes', 0)
        
        if recent_requests > 5:  # Only check if we have enough data
            success_rate = recent_successes / recent_requests
            if success_rate < 0.3:  # Less than 30% success rate
                return False
        
        return True

    def _get_preferred_provider_order(self, preferred_provider: str = None) -> List[str]:
        """
        Get provider order prioritizing preferred provider and recovery checks
        """
        available_providers = []
        
        # First, add preferred provider if specified and available
        if preferred_provider and preferred_provider in self.providers:
            if self.providers[preferred_provider].get('enabled', True):
                if self._check_provider_recovery(preferred_provider):
                    available_providers.append(preferred_provider)
                    if self.verbose:
                        verbose_print(f"🎯 Prioritizing recovered preferred provider: {preferred_provider}", self.verbose)
        
        # Then add other providers based on priority and recovery status
        for provider_name, config in self.providers.items():
            if provider_name == preferred_provider:
                continue  # Already handled above
                
            if not config.get('enabled', True):
                continue
                
            if self._check_provider_recovery(provider_name):
                available_providers.append(provider_name)
        
        # Sort by priority (assuming higher priority number = higher priority)
        available_providers.sort(key=lambda p: self.providers[p].get('priority', 0), reverse=True)
        
        return available_providers
    
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
            verbose_print(f"🔴 {provider_name} key flagged for {duration:.0f} minutes due to {error_type}", self.verbose)
    
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
    
    def _get_available_providers(self, preferred_provider: str = None) -> List[Tuple[str, Dict]]:
        """Get list of available providers sorted by priority and recovery status"""
        # Use the new provider ordering that considers recovery
        provider_order = self._get_preferred_provider_order(preferred_provider)
        
        available = []
        for provider_name in provider_order:
            if provider_name in self.providers:
                config = self.providers[provider_name]
                if config.get('enabled', True):
                    available.append((provider_name, config))
        
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
    
    # =============================================
    # AUTODECIDE FEATURE METHODS
    # =============================================
    
    def normalize_model_name(self, model_name: str) -> str:
        """Convert model names to comparable format for matching"""
        if not model_name:
            return ""
        
        normalized = model_name.lower()
        # Remove provider prefixes like "provider-1/", "@cf/meta/", "anthropic/"
        normalized = re.sub(r'^@[^/]+/', '', normalized)  # Remove "@cf/" first
        normalized = re.sub(r'^[^/]+/', '', normalized)   # Then remove other prefixes
        # Remove special characters and normalize separators
        normalized = re.sub(r'[-_.]', '', normalized)
        return normalized
    
    def model_matches(self, requested: str, available: str) -> bool:
        """Check if requested model matches available model using normalized comparison"""
        if not requested or not available:
            return False
        
        req_norm = self.normalize_model_name(requested)
        avail_norm = self.normalize_model_name(available)
        
        # Check for exact match or substring match
        return (req_norm == avail_norm or 
                req_norm in avail_norm or 
                avail_norm in req_norm)
    
    def _get_provider_models(self, provider_name: str) -> List[str]:
        """Get list of models from a specific provider"""
        config = self.providers.get(provider_name)
        if not config or not config.get('model_endpoint'):
            return []
        
        try:
            endpoint = config['model_endpoint']
            headers = {}
            
            # Add authentication if required
            if config.get('model_endpoint_auth', False):
                api_keys = config.get('api_keys', [])
                valid_keys = [key for key in api_keys if key is not None]
                if not valid_keys:
                    return []
                
                current_key = valid_keys[0]  # Use first available key
                
                auth_type = config.get('auth_type', 'bearer')
                if auth_type == 'bearer':
                    headers['Authorization'] = f'Bearer {current_key}'
                elif auth_type == 'bearer_lowercase':
                    headers['authorization'] = f'Bearer {current_key}'
            
            # Use shorter timeout for model discovery to enable faster threading
            timeout = min(config.get('timeout', 60), 10)  # Max 10 seconds for model discovery
            response = requests.get(endpoint, headers=headers, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response formats
                if 'data' in data and isinstance(data['data'], list):
                    # OpenAI format
                    return [model.get('id', '') for model in data['data']]
                elif isinstance(data, list):
                    # Direct list format
                    return [model.get('id', model.get('name', str(model))) if isinstance(model, dict) else str(model) for model in data]
                elif 'models' in data:
                    # Some providers use 'models' key
                    return [model.get('id', model.get('name', str(model))) if isinstance(model, dict) else str(model) for model in data['models']]
                
            return []
        except Exception as e:
            if self.verbose:
                verbose_print(f"❌ Failed to get models from {provider_name}: {e}", self.verbose)
            return []

    def _get_provider_models_threaded(self, provider_name: str, config: dict, results: dict, timeout_seconds: int = 10):
        """Thread-safe version of _get_provider_models for concurrent execution"""
        try:
            if not config.get('model_endpoint'):
                results[provider_name] = []
                return
            
            endpoint = config['model_endpoint']
            headers = {}
            
            # Add authentication if required
            if config.get('model_endpoint_auth', False):
                api_keys = config.get('api_keys', [])
                valid_keys = [key for key in api_keys if key is not None]
                if not valid_keys:
                    results[provider_name] = []
                    return
                
                current_key = valid_keys[0]
                auth_type = config.get('auth_type', 'bearer')
                if auth_type == 'bearer':
                    headers['Authorization'] = f'Bearer {current_key}'
                elif auth_type == 'bearer_lowercase':
                    headers['authorization'] = f'Bearer {current_key}'
            
            response = requests.get(endpoint, headers=headers, timeout=timeout_seconds)
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response formats
                if 'data' in data and isinstance(data['data'], list):
                    # OpenAI format
                    models = [model.get('id', '') for model in data['data']]
                elif isinstance(data, list):
                    # Direct list format
                    models = [model.get('id', model.get('name', str(model))) if isinstance(model, dict) else str(model) for model in data]
                elif 'models' in data:
                    # Some providers use 'models' key
                    models = [model.get('id', model.get('name', str(model))) if isinstance(model, dict) else str(model) for model in data['models']]
                else:
                    models = []
                
                results[provider_name] = models
            else:
                results[provider_name] = []
                
        except Exception as e:
            if self.verbose:
                verbose_print(f"❌ Failed to get models from {provider_name}: {e}", self.verbose)
            results[provider_name] = []
    
    def _is_cache_valid(self, model_name: str) -> bool:
        """Check if cached model data is still valid"""
        if model_name not in self.autodecide_cache_timestamps:
            return False
        
        cache_time = self.autodecide_cache_timestamps[model_name]
        cache_duration = self.autodecide_config.get("cache_duration", 1800)
        
        return (time.time() - cache_time) < cache_duration
    
    def _discover_model_providers(self, requested_model: str) -> List[Tuple[str, str]]:
        """Discover which providers have the requested model using shared cache"""
        verbose_print(f"🔍 Discovering providers for model: {requested_model}", self.verbose)
        
        # Store the requested model for discovery function
        self._current_requested_model = requested_model
        
        # Use shared cache from server if available
        if not shared_model_cache.is_cache_valid():
            shared_model_cache.load_cache()
        
        if shared_model_cache.is_cache_valid():
            providers_with_model = shared_model_cache.find_providers_for_model(requested_model)
            verbose_print(f"� Found {len(providers_with_model)} providers for {requested_model} from shared cache", self.verbose)
            return providers_with_model
        
        # Fallback to manual discovery if no shared cache
        verbose_print("⚠️ No valid shared cache available, attempting to discover models...", self.verbose)
        return self._discover_and_cache_models_sync()
    
    def _discover_and_cache_models_sync(self) -> List[Tuple[str, str]]:
        """Synchronous wrapper for model discovery and caching"""
        try:
            verbose_print("🔄 Starting model discovery from AI_engine...", self.verbose)
            
            # Create new event loop for model discovery
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._discover_and_cache_models())
                return result
            finally:
                loop.close()
        except Exception as e:
            verbose_print(f"❌ Error in model discovery: {e}", self.verbose)
            return []
    
    async def _discover_and_cache_models(self) -> List[Tuple[str, str]]:
        """Discover models from all providers and cache the results (similar to server logic)"""
        try:
            all_models = []
            enabled_providers = {name: config for name, config in AI_CONFIGS.items() if config.get('enabled', True)}
            
            if not enabled_providers:
                verbose_print("❌ No enabled providers found for model discovery", self.verbose)
                return []
            
            verbose_print(f"🔍 Discovering models from {len(enabled_providers)} providers...", self.verbose)
            
            def discover_provider_models_sync(provider_name):
                """Synchronous wrapper for provider model discovery"""
                try:
                    config = enabled_providers[provider_name]
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        models_response = loop.run_until_complete(self._discover_provider_models_internal(provider_name, config))
                        return models_response
                    finally:
                        loop.close()
                except Exception as e:
                    verbose_print(f"❌ Error discovering models for {provider_name}: {e}", self.verbose)
                    return None
            
            # Use threading for faster model discovery
            max_workers = min(len(enabled_providers), 8)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all discovery tasks
                future_to_provider = {
                    executor.submit(discover_provider_models_sync, provider_name): (provider_name, config)
                    for provider_name, config in enabled_providers.items()
                    if config.get('model_endpoint')  # Only for providers with model discovery
                }
                
                # Add providers without model discovery immediately
                for provider_name, config in enabled_providers.items():
                    if not config.get('model_endpoint'):
                        current_model = config.get('model', 'unknown')
                        all_models.append(f"{provider_name}|{current_model}")
                
                # Collect results with timeout handling
                try:
                    for future in concurrent.futures.as_completed(future_to_provider, timeout=30):
                        provider_name, config = future_to_provider[future]
                        try:
                            models_response = future.result(timeout=10)
                            
                            if models_response and 'models' in models_response:
                                provider_models = models_response['models']
                                
                                # Add models to the response
                                for model in provider_models:
                                    all_models.append(f"{provider_name}|{model}")
                                verbose_print(f"✅ {provider_name}: discovered {len(provider_models)} models", self.verbose)
                            else:
                                # Fallback to current configured model if discovery fails
                                current_model = config.get('model', 'unknown')
                                all_models.append(f"{provider_name}|{current_model}")
                                verbose_print(f"⚠️ {provider_name}: fallback to default model", self.verbose)
                                
                        except Exception as e:
                            verbose_print(f"❌ Error processing {provider_name}: {e}", self.verbose)
                            # Fallback to current model
                            current_model = config.get('model', 'unknown')
                            all_models.append(f"{provider_name}|{current_model}")
                            
                except concurrent.futures.TimeoutError:
                    # Handle unfinished futures
                    unfinished_count = 0
                    for future in future_to_provider:
                        if not future.done():
                            provider_name, config = future_to_provider[future]
                            verbose_print(f"⏰ Timeout: {provider_name} - using fallback", self.verbose)
                            # Cancel and add fallback
                            future.cancel()
                            current_model = config.get('model', 'unknown')
                            all_models.append(f"{provider_name}|{current_model}")
                            unfinished_count += 1
                    verbose_print(f"⚠️ {unfinished_count} providers timed out, used fallbacks", self.verbose)

            verbose_print(f"✅ Model discovery completed. Found {len(all_models)} models total.", self.verbose)

            # Cache the discovered models
            shared_model_cache.save_cache(all_models)
            
            # Now find the requested model from the cached models
            requested_model = getattr(self, '_current_requested_model', None)
            if requested_model:
                return shared_model_cache.find_providers_for_model(requested_model)
            
            return []

        except Exception as e:
            verbose_print(f"❌ Error in model discovery: {e}", self.verbose)
            return []
    
    async def _discover_provider_models_internal(self, provider_name: str, config: Dict[str, Any]) -> Optional[Dict]:
        """Internal method to discover models from a specific provider"""
        model_endpoint = config.get('model_endpoint')
        if not model_endpoint:
            return None
            
        headers = {}
        auth_header = config.get('auth_header', 'Authorization')
        
        # Get API key (supporting multiple key formats)
        api_key = None
        api_keys = config.get('api_keys', [])
        if api_keys:
            api_key = api_keys[0] if isinstance(api_keys, list) else api_keys
        else:
            api_key = config.get('api_key')
        
        if api_key:
            if auth_header == 'Authorization':
                headers[auth_header] = f"Bearer {api_key}"
            else:
                headers[auth_header] = api_key
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(model_endpoint, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Handle different response formats
                        if isinstance(data, dict):
                            if 'data' in data and isinstance(data['data'], list):
                                # OpenAI format
                                models = [model.get('id', '') for model in data['data'] if model.get('id')]
                            elif 'models' in data:
                                # Direct models array
                                models = data['models'] if isinstance(data['models'], list) else []
                            elif isinstance(data, list):
                                # Direct array
                                models = [str(item) for item in data]
                            else:
                                models = []
                        elif isinstance(data, list):
                            models = [str(item) for item in data]
                        else:
                            models = []
                        
                        # Clean up model names (remove provider prefix if present)
                        clean_models = []
                        for model in models:
                            if isinstance(model, dict):
                                model_id = model.get('id', str(model))
                            else:
                                model_id = str(model)
                            
                            # Remove provider prefix if present
                            if '/' in model_id:
                                model_id = model_id.split('/', 1)[1]
                            
                            if model_id and model_id not in clean_models:
                                clean_models.append(model_id)
                        
                        return {"models": clean_models}
                    else:
                        verbose_print(f"❌ {provider_name}: HTTP {response.status}", self.verbose)
                        return None
                        
        except Exception as e:
            verbose_print(f"❌ {provider_name}: {str(e)}", self.verbose)
            return None
    
    def _select_best_provider(self, available_providers: List[Tuple[str, str]]) -> Tuple[str, str]:
        """Select best provider from available options based on priority and performance"""
        if not available_providers:
            return None, None
        
        # Filter out flagged providers first
        working_providers = [
            (provider_name, model_name) for provider_name, model_name in available_providers
            if not self._is_key_flagged(provider_name)
        ]
        
        if not working_providers:
            if self.verbose:
                verbose_print("⚠️ All providers are flagged, falling back to any available provider", self.verbose)
            working_providers = available_providers
        
        # Sort by multiple criteria:
        # 1. Priority (lower number = higher priority)
        # 2. Performance score from statistics (if available)
        # 3. Provider name (for consistency)
        
        def get_provider_score(provider_tuple):
            provider_name, model_name = provider_tuple
            config = self.providers.get(provider_name, {})
            
            # Priority (lower = better, so we use it directly for sorting)
            priority = config.get('priority', 999)
            
            # Performance score from statistics (higher = better, so we negate for sorting)
            performance_score = 0
            if hasattr(self, 'statistics_manager') and self.statistics_manager:
                try:
                    stats = self.statistics_manager.get_provider_stats(provider_name)
                    if stats:
                        success_rate = stats.get('success_rate', 0)
                        avg_response_time = stats.get('average_response_time', 5.0)
                        # Calculate performance score (success rate 70%, speed 30%)
                        speed_score = max(0, 100 - (avg_response_time * 10))
                        performance_score = -(success_rate * 0.7 + speed_score * 0.3)  # Negative for ascending sort
                except:
                    pass
            
            # Flagged status penalty
            flagged_penalty = 1000 if self._is_key_flagged(provider_name) else 0
            
            return (priority, performance_score, flagged_penalty, provider_name)
        
        # Sort providers by score
        sorted_providers = sorted(working_providers, key=get_provider_score)
        
        # Return the best provider
        best_provider_name, best_model_name = sorted_providers[0]
        
        if self.verbose:
            config = self.providers.get(best_provider_name, {})
            priority = config.get('priority', 999)
            verbose_print(f"🎯 Selected {best_provider_name} with model '{best_model_name}' (priority: {priority})", self.verbose)
            
            # Show alternatives if there are any
            if len(sorted_providers) > 1:
                alternatives = sorted_providers[1:4]  # Show up to 3 alternatives
                alt_info = ", ".join([f"{p}(pri:{self.providers.get(p, {}).get('priority', '?')})" 
                                    for p, m in alternatives])
                verbose_print(f"🔄 Alternatives available: {alt_info}", self.verbose)
        
        return best_provider_name, best_model_name
        
        # If all are flagged, return the first one anyway
        provider_name, model_name = sorted_providers[0]
        if self.verbose:
            verbose_print(f"⚠️ Selected {provider_name} with model '{model_name}' (flagged but best available, self.verbose)")
        return provider_name, model_name

    def chat_completion(self, messages: List[Dict[str, str]], model: str = None, autodecide: bool = True, **kwargs) -> RequestResult:
        """
        Main chat completion method with smart provider rotation and autodecide feature
        Supports provider-specific routing with format: provider_name/model_name
        """
        start_time = time.time()  # Track total request time
        preferred_provider = kwargs.get('preferred_provider')
        force_provider = kwargs.get('force_provider', False)  # New option to force specific provider only
        
        # Parse provider/model format (e.g., "openai/gpt-4" or "anthropic/claude-3")
        original_model = model
        if model and '/' in model:
            provider_part, model_part = model.split('/', 1)
            # Check if the provider part is a valid provider name
            if provider_part in self.providers:
                preferred_provider = provider_part
                model = model_part
                force_provider = True  # Force the specified provider
                if self.verbose:
                    verbose_print(f"🎯 Parsed provider-specific request: {provider_part}/{model_part}", self.verbose)
            else:
                if self.verbose:
                    verbose_print(f"⚠️ Unknown provider in '{original_model}', treating as model name", self.verbose)
        
        # If force_provider is True and preferred_provider is specified, only use that provider
        if force_provider and preferred_provider:
            if preferred_provider not in self.providers:
                return RequestResult(
                    success=False,
                    error_message=f"Forced provider '{preferred_provider}' not found in configuration",
                    error_type="provider_not_found"
                )
            
            if not self.providers[preferred_provider].get('enabled', True):
                return RequestResult(
                    success=False,
                    error_message=f"Forced provider '{preferred_provider}' is disabled",
                    error_type="provider_disabled"
                )
            
            # Check if provider is flagged and handle accordingly
            if self._is_key_flagged(preferred_provider):
                # For forced provider, we'll try anyway but warn
                if self.verbose:
                    verbose_print(f"⚠️ Forcing flagged provider: {preferred_provider}", self.verbose)
            
            provider_config = self.providers[preferred_provider]
            start_time = time.time()
            
            try:
                if self.verbose:
                    verbose_print(f"🔒 Force using provider: {preferred_provider} with model: {model or 'default'}", self.verbose)
                
                result = self._make_request(preferred_provider, provider_config, messages, model, **kwargs)
                response_time = time.time() - start_time
                
                self._update_stats(preferred_provider, result.success, response_time)
                
                result.provider_used = preferred_provider
                result.response_time = response_time
                self.current_provider = preferred_provider
                
                if result.success:
                    self._handle_provider_success(preferred_provider, response_time)
                    if self.verbose:
                        verbose_print(f"✅ Forced provider {preferred_provider} successful ({response_time:.2f}s, self.verbose)")
                else:
                    if self.verbose:
                        verbose_print(f"❌ Forced provider {preferred_provider} failed: {result.error_message}", self.verbose)
                
                return result
                
            except Exception as e:
                error_msg = f"Exception with forced provider {preferred_provider}: {str(e)}"
                if self.verbose:
                    verbose_print(f"❌ {error_msg}", self.verbose)
                return RequestResult(
                    success=False,
                    error_message=error_msg,
                    error_type="provider_exception",
                    provider_used=preferred_provider,
                    response_time=time.time() - start_time
                )
        
        # AUTODECIDE FEATURE: If enabled and model is specified, try to find best provider
        if (autodecide and 
            self.autodecide_config.get("enabled", True) and 
            model and 
            not preferred_provider):  # Don't override preferred provider
            
            # Discover providers for this model using shared cache
            available_providers = self._discover_model_providers(model)
            if available_providers:
                # Select best provider by priority
                best_provider, actual_model = self._select_best_provider(available_providers)
                if best_provider:
                    preferred_provider = best_provider
                    model = actual_model  # Use the exact model name from the provider
                    verbose_print(f"🤖 Autodecide selected {best_provider} with model '{actual_model}'", self.verbose)
                else:
                    # All providers are flagged/unavailable
                    return RequestResult(
                        success=False,
                        error_message=f"Model '{model}' is available but all providers are currently unavailable or flagged",
                        error_type="providers_unavailable",
                        response_time=time.time() - start_time
                    )
            else:
                # No providers found for the requested model - strict matching failed
                return RequestResult(
                    success=False,
                    error_message=f"Model '{model}' is not available in any of the configured providers. Please check the model name or try a different model.",
                    error_type="model_not_found",
                    response_time=time.time() - start_time
                )
        
        # If a preferred provider is specified, try it first
        if preferred_provider:
            if preferred_provider in self.providers and not self._is_key_flagged(preferred_provider):
                provider_config = self.providers[preferred_provider]
                start_time = time.time()
                
                try:
                    if self.verbose:
                        verbose_print(f"🎯 Using preferred provider: {preferred_provider}", self.verbose)
                    
                    result = self._make_request(preferred_provider, provider_config, messages, model, **kwargs)
                    response_time = time.time() - start_time
                    
                    self._update_stats(preferred_provider, result.success, response_time)
                    
                    if result.success:
                        result.provider_used = preferred_provider
                        result.response_time = response_time
                        self.current_provider = preferred_provider
                        return result
                    else:
                        if self.verbose:
                            verbose_print(f"❌ Preferred provider {preferred_provider} failed: {result.error_message}", self.verbose)
                except Exception as e:
                    if self.verbose:
                        verbose_print(f"❌ Exception with preferred provider {preferred_provider}: {e}", self.verbose)
            else:
                if self.verbose:
                    verbose_print(f"⚠️ Preferred provider {preferred_provider} not available or flagged", self.verbose)
        
        # Fall back to normal provider rotation with recovery awareness
        available_providers = self._get_available_providers(preferred_provider)
        
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
                    verbose_print(f"🔄 Trying {provider_name}...", self.verbose)
                
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
                        verbose_print(f"✅ {provider_name} successful ({response_time:.2f}s, self.verbose)")
                    
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
                        verbose_print(f"❌ {provider_name} failed: {result.error_message}", self.verbose)
                    
                    # Continue to next provider (automatic provider rotation)
                    continue
                    
            except Exception as e:
                response_time = time.time() - start_time
                self._update_stats(provider_name, False, response_time)
                
                # Handle exception as failure with enhanced tracking
                self._handle_provider_failure(provider_name, str(e), 0, None)
                
                if self.verbose:
                    verbose_print(f"💥 {provider_name} exception: {str(e, self.verbose)}")
                
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
        used_model = model or config['model']
        data = {
            'model': used_model,
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
                    model_used=used_model,
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
        
        # Determine the model to use
        used_model = model or config['model']
        
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
                    model_used=used_model,
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
        
        # Determine the model to use
        used_model = model or config['model']
        
        # Convert to Cohere v2 format - uses messages array directly
        data = {
            "model": used_model,
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
                    model_used=used_model,
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
    
    def stress_test_providers(self, test_iterations: int = 3, ask_for_priority_change: bool = True, use_threading: bool = True) -> Dict[str, Any]:
        """
        Run stress test on all providers and optionally ask user for priority changes
        Enhanced with threading for faster execution
        """
        enabled_providers = {name: config for name, config in self.providers.items() if config.get('enabled', True)}
        
        print(f"🧪 Starting stress test on {len(enabled_providers)} enabled providers...")
        print(f"📝 Test iterations: {test_iterations}")
        print(f"⚡ Threading enabled: {use_threading}")
        print()
        
        test_prompt = "Hello! Please respond with exactly: 'Test successful - AI Engine v3.0 working!'"
        results = {}
        
        if use_threading and len(enabled_providers) > 1:
            # Use threading for faster stress testing
            results = self._stress_test_threaded(enabled_providers, test_iterations, test_prompt)
        else:
            # Sequential testing (original method)
            results = self._stress_test_sequential(enabled_providers, test_iterations, test_prompt)
        
        # Calculate overall stats
        total_providers = len(results)
        passed_providers = sum(1 for r in results.values() if r['passed'])
        pass_rate = (passed_providers / total_providers) * 100 if total_providers > 0 else 0
        
        print(f"\n📊 STRESS TEST SUMMARY:")
        print(f"Providers tested: {total_providers}")
        print(f"Providers passed: {passed_providers}")
        print(f"Overall pass rate: {pass_rate:.1f}%")
        
        # Show detailed results
        print(f"\n📋 DETAILED RESULTS:")
        print(f"{'Provider':<15} {'Status':<6} {'Success Rate':<12} {'Avg Time':<10} {'Priority'}")
        print("-" * 65)
        
        # Sort by current priority for display
        sorted_results = sorted(results.items(), key=lambda x: self.providers.get(x[0], {}).get('priority', 999))
        
        for provider_name, result in sorted_results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            success_rate = f"{result['success_rate']:.1f}%"
            avg_time = f"{result['avg_response_time']:.2f}s"
            priority = self.providers.get(provider_name, {}).get('priority', '?')
            
            print(f"{provider_name:<15} {status:<6} {success_rate:<12} {avg_time:<10} {priority}")
        
        # Ask user about priority changes if requested
        if ask_for_priority_change and passed_providers > 0:
            print(f"\n🔄 Priority Optimization Available")
            print(f"Current priority ranking vs. performance-based ranking could be optimized.")
            print(f"This will update both in-memory priorities and save changes to config.py.")
            
            response = input("Enter 'y' to optimize priorities or 'n' to keep current: ").lower().strip()
            
            if response == 'y':
                self._optimize_priorities(results)
            else:
                print("📌 Keeping current priorities")
        
        return results

    def _stress_test_sequential(self, providers: Dict, test_iterations: int, test_prompt: str) -> Dict[str, Any]:
        """Sequential stress testing (original method)"""
        results = {}
        
        for provider_name, provider_config in providers.items():
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
        
        return results

    def _stress_test_threaded(self, providers: Dict, test_iterations: int, test_prompt: str) -> Dict[str, Any]:
        """Threaded stress testing for faster execution"""
        results = {}
        max_workers = min(len(providers), 8)  # Limit concurrent tests
        
        print(f"⚡ Running threaded stress test with {max_workers} workers...")
        
        def test_provider(provider_item):
            provider_name, provider_config = provider_item
            provider_results = {
                'provider': provider_name,
                'total_tests': test_iterations,
                'successful_tests': 0,
                'failed_tests': 0,
                'response_times': [],
                'errors': []
            }
            
            print(f"🧪 Testing {provider_name}...")
            
            for i in range(test_iterations):
                start_time = time.time()
                try:
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
                            'error_type': getattr(result, 'error_type', 'unknown')
                        })
                except Exception as e:
                    response_time = time.time() - start_time
                    provider_results['failed_tests'] += 1
                    provider_results['errors'].append({
                        'iteration': i + 1,
                        'error': str(e),
                        'error_type': 'exception'
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
            
            status = "✅ PASS" if provider_results['passed'] else "❌ FAIL"
            print(f"✅ {provider_name}: {status} ({success_rate:.1f}%, {avg_response_time:.2f}s)")
            
            return provider_name, provider_results
        
        # Execute tests in parallel
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_provider = {
                executor.submit(test_provider, provider_item): provider_item[0]
                for provider_item in providers.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_provider):
                try:
                    provider_name, provider_results = future.result(timeout=60)  # 60 second timeout per provider
                    results[provider_name] = provider_results
                except Exception as e:
                    provider_name = future_to_provider[future]
                    print(f"❌ {provider_name} test failed with exception: {e}")
                    # Create a failed result
                    results[provider_name] = {
                        'provider': provider_name,
                        'total_tests': test_iterations,
                        'successful_tests': 0,
                        'failed_tests': test_iterations,
                        'response_times': [],
                        'errors': [{'iteration': 'all', 'error': str(e), 'error_type': 'timeout_exception'}],
                        'success_rate': 0,
                        'avg_response_time': 0,
                        'min_response_time': 0,
                        'max_response_time': 0,
                        'passed': False
                    }
        
        total_time = time.time() - start_time
        print(f"⏱️ Threaded stress test completed in {total_time:.2f}s")
        
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
        
        print(f"\n🏆 OPTIMIZED PRIORITY RANKING:")
        print(f"{'Rank':<4} {'Provider':<15} {'Score':<6} {'Time':<7} {'Old Pri':<7} {'New Pri'}")
        print("-" * 60)
        
        # Update priorities and prepare changes to save
        priority_changes = {}
        for i, (provider_name, score, avg_time) in enumerate(provider_scores, 1):
            old_priority = self.providers[provider_name].get('priority', 999)
            new_priority = i
            
            # Update in-memory configuration
            self.providers[provider_name]['priority'] = new_priority
            
            # Track changes for file saving
            if old_priority != new_priority:
                priority_changes[provider_name] = new_priority
            
            print(f"{i:2d}   {provider_name:15} {score:5.1f}  {avg_time:5.2f}s  {old_priority:5d}   {new_priority:5d}")
        
        # Save changes to config.py file
        if priority_changes:
            try:
                self._save_priority_changes_to_config(priority_changes)
                print(f"\n✅ Priority changes saved to config.py")
                print(f"📝 Updated {len(priority_changes)} provider priorities")
            except Exception as e:
                print(f"\n⚠️ Failed to save priority changes to config.py: {e}")
                print(f"📝 In-memory priorities updated, but file changes not saved")
        else:
            print(f"\n📌 No priority changes needed")

    def _save_priority_changes_to_config(self, priority_changes: Dict[str, int]):
        """Save priority changes back to config.py file"""
        try:
            # Read the current config file
            with open('config.py', 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # Apply each priority change
            updated_content = config_content
            
            for provider_name, new_priority in priority_changes.items():
                # Create a pattern to find and replace the priority line for this provider
                # Look for the provider section and the priority field within it
                provider_pattern = rf'"{provider_name}":\s*\{{([^}}]*)"priority":\s*\d+([^}}]*)}}'
                
                def replace_priority(match):
                    before_priority = match.group(1)
                    after_priority = match.group(2)
                    return f'"{provider_name}": {{{before_priority}"priority": {new_priority}{after_priority}}}'
                
                updated_content = re.sub(provider_pattern, replace_priority, updated_content, flags=re.DOTALL)
            
            # Write the updated config back to file
            with open('config.py', 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            print(f"📁 Config file updated with new priorities")
            
        except Exception as e:
            raise Exception(f"Failed to update config.py: {str(e)}")
    
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
                verbose_print(f"🧪 Testing {provider_name} specifically...", self.verbose)
            
            result = self._make_request(provider_name, provider_config, messages)
            response_time = time.time() - start_time
            
            # Update stats
            self._update_stats(provider_name, result.success, response_time)
            
            if result.success:
                result.provider_used = provider_name
                result.response_time = response_time
                
                if self.verbose:
                    verbose_print(f"✅ {provider_name} test successful ({response_time:.2f}s, self.verbose)")
            else:
                # Handle errors and flagging
                error_type = self._classify_error(result.error_message, result.status_code)
                
                if error_type in ["rate_limit", "daily_limit", "auth_error"]:
                    self._flag_key(provider_name, error_type)
                
                if self.verbose:
                    verbose_print(f"❌ {provider_name} test failed: {result.error_message}", self.verbose)
            
            return result
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(provider_name, False, response_time)
            
            if self.verbose:
                verbose_print(f"💥 {provider_name} exception: {str(e, self.verbose)}")
            
            return RequestResult(
                success=False,
                error_message=str(e),
                error_type="request_exception",
                response_time=response_time
            )

    def save_statistics_now(self):
        """Manually save current statistics to persistent storage"""
        save_statistics_now()
        if self.verbose:
            verbose_print("Statistics saved manually", self.verbose)
    
    def roll_api_key(self, provider_name: str) -> str:
        """Manually roll to the next API key for a provider"""
        if provider_name not in self.providers:
            return f"Provider {provider_name} not found"
        
        config = self.providers[provider_name]
        api_keys = config.get('api_keys', [])
        
        if len(api_keys) <= 1:
            return f"Provider {provider_name} has only {len(api_keys)} key(s), no rolling needed"
        
        # Get current key index
        current_index = self.provider_key_rotation.get(provider_name, 0)
        current_key = api_keys[current_index] if current_index < len(api_keys) else None
        current_key_preview = current_key[:8] + "..." if current_key and len(current_key) > 8 else current_key
        
        # Rotate to next key
        new_key = self._rotate_api_key(provider_name)
        new_index = self.provider_key_rotation.get(provider_name, 0)
        new_key_preview = new_key[:8] + "..." if new_key and len(new_key) > 8 else new_key
        
        if new_key and new_key != current_key:
            return f"✅ Rolled from key #{current_index} ({current_key_preview}) to key #{new_index} ({new_key_preview})"
        elif not self.engine_settings.get('key_rotation_enabled', True):
            return f"⚠️ Key rotation is disabled in engine settings"
        else:
            return f"🔄 Key rolling attempted: staying at key #{current_index} ({current_key_preview}) - may be optimal choice"
    
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
    import atexit
    
    # Initialize engine
    engine = None
    
    def cleanup():
        """Save statistics on exit"""
        if engine:
            try:
                engine.save_statistics_now()
            except:
                pass
    
    # Register cleanup function
    atexit.register(cleanup)
    
    # Check for command-line arguments
    if len(sys.argv) > 1:
        provider_name = sys.argv[1].lower()
        
        # Handle special commands
        if provider_name == "stress":
            engine = AI_engine(verbose=True)
            print("🧪 Running comprehensive stress test...")
            results = engine.stress_test_providers(test_iterations=3, ask_for_priority_change=True)
            return
        elif provider_name == "server":
            print("🚀 Starting AI Engine FastAPI Server...")
            try:
                from server import main as server_main
                server_main()
            except ImportError as e:
                print(f"❌ Server module not found: {e}")
                print("Make sure server.py is in the same directory and requirements are installed:")
                print("pip install -r requirements_server.txt")
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
        elif provider_name == "autodecide":
            # Autodecide mode - automatically find best provider for specified model
            engine = AI_engine()  # Use global config for verbose mode
            
            if len(sys.argv) < 3:
                print("❌ Usage: python ai_engine.py autodecide <model_name> [message]")
                print("📋 Examples:")
                print("   python ai_engine.py autodecide gpt-4 'Hello world'")
                print("   python ai_engine.py autodecide claude 'Test message'")
                print("   python ai_engine.py autodecide llama 'Quick test'")
                return
            
            target_model = sys.argv[2]
            custom_message = "Hello! Please respond with a short test message."
            if len(sys.argv) > 3:
                custom_message = " ".join(sys.argv[3:])
            
            print(f"🎯 Testing autodecide for model: {target_model}")
            print("-" * 50)
            
            # Discover providers for this model
            providers = engine._discover_model_providers(target_model)
            if providers:
                verbose_print(f"� Found {len(providers)} providers supporting '{target_model}':", engine.verbose)
                for i, (provider_name, provider_model) in enumerate(providers[:5], 1):
                    verbose_print(f"  {i}. {provider_name}: {provider_model}", engine.verbose)
                if len(providers) > 5:
                    verbose_print(f"     ... and {len(providers) - 5} more providers", engine.verbose)
            else:
                verbose_print(f"⚠️  No providers found for model '{target_model}'", engine.verbose)
                verbose_print("🔄 Falling back to automatic provider selection...", engine.verbose)
            
            print(f"\n🚀 Making autodecide chat completion...")
            messages = [{"role": "user", "content": custom_message}]
            result = engine.chat_completion(messages, model=target_model, autodecide=True)
            
            if result.success:
                print(f"✅ AUTODECIDE SUCCESS!")
                print(f"🎯 Requested model: {target_model}")
                print(f"🏃‍♂️ Provider selected: {result.provider_used}")
                print(f"🤖 Model used: {result.model_used}")
                print(f"💬 Response: {result.content}")
                print(f"⏱️ Response time: {result.response_time:.2f}s")
            else:
                print(f"❌ AUTODECIDE FAILED!")
                print(f"🎯 Requested model: {target_model}")
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
    print(f"  python ai_engine.py server             # Start FastAPI web server")

if __name__ == "__main__":
    main()

# Convenience function for easy import
def get_ai_engine(verbose: bool = False) -> 'AI_engine':
    """
    Convenience function to get an AI_engine instance
    
    Args:
        verbose (bool): Enable verbose logging
        
    Returns:
        AI_engine: Configured AI Engine instance
    """
    return AI_engine(verbose=verbose)
