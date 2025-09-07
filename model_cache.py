"""
Shared Model Cache System for AI Engine
Provides centralized model caching for both server and autodecide features
"""

import json
import time
import os
import threading
from typing import List, Dict, Any, Optional, Tuple
from config import verbose_print

class ModelCache:
    """Centralized model cache with auto-refresh capability"""
    
    def __init__(self):
        self.cache_file = "model_cache.json"
        self.cache_duration = 30 * 60  # 30 minutes in seconds
        self.cache_data = {
            "cached_at": None,
            "models": [],
            "providers": {}
        }
        self.auto_refresh_thread = None
        self.auto_refresh_active = False
        self._lock = threading.Lock()
    
    def load_cache(self) -> bool:
        """Load models data from cache file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if cache is still valid (within 30 minutes)
                if cache_data.get("cached_at"):
                    cache_age = time.time() - cache_data["cached_at"]
                    if cache_age <= self.cache_duration:
                        with self._lock:
                            self.cache_data = cache_data
                        verbose_print(f"📦 Loaded {len(cache_data.get('models', []))} models from cache (age: {cache_age/60:.1f} minutes)")
                        return True
                    else:
                        verbose_print(f"⏰ Model cache expired (age: {cache_age/60:.1f} minutes)")
        except Exception as e:
            verbose_print(f"❌ Error loading model cache: {e}")
        
        return False
    
    def save_cache(self, models_data: List[Dict], providers_data: Dict = None) -> None:
        """Save models data to cache file"""
        try:
            cache_data = {
                "cached_at": time.time(),
                "models": models_data,
                "providers": providers_data or {}
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            with self._lock:
                self.cache_data = cache_data
                
            print(f"✅ Model discovery completed. Found {len(models_data)} models total.")
            verbose_print(f"💾 Saved {len(models_data)} models to cache")
        except Exception as e:
            verbose_print(f"❌ Error saving model cache: {e}")
    
    def is_cache_valid(self) -> bool:
        """Check if current cache is still valid"""
        with self._lock:
            if not self.cache_data.get("cached_at"):
                return False
            
            cache_age = time.time() - self.cache_data["cached_at"]
            return cache_age <= self.cache_duration
    
    def get_models(self) -> List[Dict]:
        """Get all cached models"""
        with self._lock:
            return self.cache_data.get("models", [])
    
    def get_providers_data(self) -> Dict:
        """Get providers data from cache"""
        with self._lock:
            return self.cache_data.get("providers", {})
    
    def get_cache_age(self) -> float:
        """Get cache age in seconds"""
        with self._lock:
            if not self.cache_data.get("cached_at"):
                return float('inf')
            return time.time() - self.cache_data["cached_at"]
    
    def find_providers_for_model(self, model_name: str) -> List[Tuple[str, str]]:
        """
        Find providers that support a specific model with STRICT matching
        Returns list of (provider_name, model_name) tuples
        Only returns exact matches - no fuzzy matching to prevent wrong model selection
        """
        providers_with_model = []
        models = self.get_models()
        
        # Normalize the requested model for comparison
        requested_normalized = self._normalize_model_name(model_name)
        
        for model_entry in models:
            # Get provider from 'owned_by' field (server cache format)
            provider = model_entry.get("owned_by", model_entry.get("provider", ""))
            model_id = model_entry.get("id", "")
            
            # Remove provider prefix from model_id if present (e.g., "groq/gpt-4" -> "gpt-4")
            clean_model_id = model_id
            if "/" in model_id:
                clean_model_id = model_id.split("/", 1)[1]
            
            # Normalize the available model for comparison
            available_normalized = self._normalize_model_name(clean_model_id)
            
            # STRICT MATCHING: Only exact matches allowed
            if requested_normalized == available_normalized:
                providers_with_model.append((provider, clean_model_id))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_providers = []
        for provider, model in providers_with_model:
            key = (provider, model)
            if key not in seen:
                seen.add(key)
                unique_providers.append(key)
        
        return unique_providers
    
    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name for comparison"""
        if not model_name:
            return ""
        return model_name.lower().replace("-", "").replace("_", "").replace(".", "")
    
    def start_auto_refresh(self, refresh_callback):
        """Start background auto-refresh every 30 minutes"""
        if self.auto_refresh_active:
            return
        
        self.auto_refresh_active = True
        self.auto_refresh_thread = threading.Thread(
            target=self._auto_refresh_worker,
            args=(refresh_callback,),
            daemon=True
        )
        self.auto_refresh_thread.start()
        verbose_print("🔄 Started auto-refresh background task (30-minute interval)")
    
    def stop_auto_refresh(self):
        """Stop background auto-refresh"""
        self.auto_refresh_active = False
        if self.auto_refresh_thread:
            self.auto_refresh_thread.join(timeout=1)
        verbose_print("⏹️ Stopped auto-refresh background task")
    
    def _auto_refresh_worker(self, refresh_callback):
        """Background worker for auto-refresh"""
        while self.auto_refresh_active:
            time.sleep(self.cache_duration)  # Wait 30 minutes
            
            if self.auto_refresh_active:  # Check again after sleep
                verbose_print("🔄 Auto-refreshing model cache...")
                try:
                    refresh_callback()
                    verbose_print("✅ Auto-refresh completed successfully")
                except Exception as e:
                    verbose_print(f"❌ Auto-refresh failed: {e}")

# Global shared cache instance
shared_model_cache = ModelCache()
