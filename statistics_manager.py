"""
Statistics Manager for AI Engine v3.0
Handles persistent key statistics tracking and management
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# Import verbose_print function
try:
    from config import verbose_print, ENGINE_SETTINGS
except ImportError:
    # Fallback verbose_print function
    def verbose_print(message: str, verbose_override: bool = None):
        # Default to False if no config available
        if verbose_override or False:
            print(message)
    ENGINE_SETTINGS = {"verbose_mode": False}

@dataclass
class KeyStatistics:
    """Statistics for a single API key"""
    requests: int = 0
    successes: int = 0
    failures: int = 0
    last_used: Optional[datetime] = None
    rate_limited: bool = False
    weight: float = 1.0
    total_response_time: float = 0.0  # For all requests (backward compatibility)
    successful_response_time: float = 0.0  # Only for successful requests

    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.requests == 0:
            return 0.0
        return (self.successes / self.requests) * 100

    def avg_successful_response_time(self) -> float:
        """Calculate average response time for successful requests only"""
        if self.successes == 0:
            return 0.0
        return self.successful_response_time / self.successes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        if self.last_used:
            data['last_used'] = self.last_used.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyStatistics':
        """Create from dictionary (handles datetime deserialization and missing fields)"""
        # Handle datetime deserialization
        if 'last_used' in data and data['last_used']:
            try:
                data['last_used'] = datetime.fromisoformat(data['last_used'])
            except:
                data['last_used'] = None
        
        # Handle backward compatibility for missing successful_response_time field
        if 'successful_response_time' not in data:
            data['successful_response_time'] = 0.0
            
        return cls(**data)

class StatisticsManager:
    """
    Manages persistent key statistics for AI Engine
    Provides clean separation between configuration and runtime data
    """

    def __init__(self, stats_file: str = "key_statistics.json", auto_save_interval: int = 30):
        self.stats_file = stats_file
        self.auto_save_interval = auto_save_interval
        self.statistics: Dict[str, Dict[str, KeyStatistics]] = {}
        self.save_task: Optional[asyncio.Task] = None
        self._load_statistics()

    def _load_statistics(self):
        """Load statistics from persistent storage"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)

                # Convert to KeyStatistics objects
                for provider_name, provider_stats in data.items():
                    self.statistics[provider_name] = {}
                    for key_id, key_data in provider_stats.items():
                        self.statistics[provider_name][key_id] = KeyStatistics.from_dict(key_data)

                verbose_print(f"📊 Loaded statistics for {len(self.statistics)} providers")
            else:
                verbose_print("📊 No existing statistics file found, starting fresh")
        except Exception as e:
            verbose_print(f"⚠️ Error loading statistics: {e}")
            self.statistics = {}

    def _save_statistics(self):
        """Save statistics to persistent storage"""
        try:
            # Convert to serializable format
            data = {}
            for provider_name, provider_stats in self.statistics.items():
                data[provider_name] = {}
                for key_id, key_stats in provider_stats.items():
                    data[provider_name][key_id] = key_stats.to_dict()

            with open(self.stats_file, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            verbose_print(f"⚠️ Error saving statistics: {e}")

    def get_statistics(self, provider_name: str, key_id: str) -> Optional[KeyStatistics]:
        """Get statistics for a specific key"""
        return self.statistics.get(provider_name, {}).get(key_id)

    def update_statistics(self, provider_name: str, key_id: str,
                        success: bool = True, response_time: float = 0.0):
        """Update statistics for a key"""
        if provider_name not in self.statistics:
            self.statistics[provider_name] = {}

        if key_id not in self.statistics[provider_name]:
            self.statistics[provider_name][key_id] = KeyStatistics()

        stats = self.statistics[provider_name][key_id]
        stats.requests += 1
        stats.last_used = datetime.now()
        stats.total_response_time += response_time

        if success:
            stats.successes += 1
            stats.successful_response_time += response_time  # Track successful response time separately
            # Improve weight for successful keys
            stats.weight = max(0.5, stats.weight * 0.95)
            stats.rate_limited = False
        else:
            stats.failures += 1
            # Penalize failing keys
            stats.weight = min(2.0, stats.weight * 1.1)

    def mark_rate_limited(self, provider_name: str, key_id: str):
        """Mark a key as rate limited"""
        if provider_name in self.statistics and key_id in self.statistics[provider_name]:
            stats = self.statistics[provider_name][key_id]
            stats.rate_limited = True
            stats.weight = 2.0  # Heavy penalty

    def get_provider_report(self, provider_name: str) -> Dict[str, Any]:
        """Get comprehensive report for all keys of a provider"""
        if provider_name not in self.statistics:
            return {}

        report = {}
        for key_id, stats in self.statistics[provider_name].items():
            key_num = int(key_id.split('_')[1]) + 1
            report[f"Key #{key_num}"] = {
                'total_requests': stats.requests,
                'successes': stats.successes,
                'failures': stats.failures,
                'requests_this_minute': 0,  # This would need current session tracking
                'rate_limited': stats.rate_limited,
                'weight': stats.weight,
                'last_used': stats.last_used,
                'success_rate': stats.success_rate()
            }

        return report

    def get_all_provider_summary(self) -> Dict[str, Any]:
        """Get summary of all providers with multi-key support"""
        summary = {}

        for provider_name, provider_stats in self.statistics.items():
            if len(provider_stats) > 1:  # Only show multi-key providers
                summary[provider_name] = {}
                for key_id, stats in provider_stats.items():
                    key_num = int(key_id.split('_')[1]) + 1
                    status = "🔴 RATE LIMITED" if stats.rate_limited else "🟢 ACTIVE"
                    summary[provider_name][f"Key #{key_num}"] = {
                        'requests': stats.requests,
                        'success_rate': f"{stats.success_rate():.1f}%",
                        'status': status
                    }

        return summary

    def start_auto_save(self):
        """Start automatic saving of statistics"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, schedule the task for later
                # This will be handled by the calling code
                pass
            else:
                self.save_task = asyncio.create_task(self._auto_save_loop())
        except RuntimeError:
            # Handle case where event loop is not running
            pass

    async def _auto_save_loop(self):
        """Background loop for automatic saving"""
        while True:
            try:
                await asyncio.sleep(self.auto_save_interval)
                self._save_statistics()
                verbose_print("💾 Statistics auto-saved")
            except Exception as e:
                verbose_print(f"⚠️ Auto-save error: {e}")
                await asyncio.sleep(self.auto_save_interval)

    def save_now(self):
        """Manually save statistics immediately"""
        self._save_statistics()

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get overall statistics summary"""
        total_providers = len(self.statistics)
        total_keys = sum(len(provider_stats) for provider_stats in self.statistics.values())
        total_requests = sum(
            stats.requests
            for provider_stats in self.statistics.values()
            for stats in provider_stats.values()
        )

        return {
            'total_providers': total_providers,
            'total_keys': total_keys,
            'total_requests': total_requests,
            'stats_file': self.stats_file
        }

# Global instance for easy access
stats_manager = StatisticsManager()

def get_stats_manager() -> StatisticsManager:
    """Get the global statistics manager instance"""
    return stats_manager

def save_statistics_now():
    """Convenience function to save statistics immediately"""
    stats_manager.save_now()

# Note: Auto-save is disabled to avoid async warnings in synchronous contexts
# Statistics will be saved manually when needed
