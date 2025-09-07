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
    
    def save_cache(self, models_data, providers_data: Dict = None) -> None:
        """Save models data to cache file in optimized format"""
        try:
            # Handle both old format (List[Dict]) and new format (List[str])
            optimized_models = []
            
            for model in models_data:
                if isinstance(model, dict):
                    # Old format: extract ID from dict
                    model_id = model.get("id", "")
                    if model_id:
                        optimized_models.append(model_id)
                elif isinstance(model, str):
                    # New format: already a string
                    optimized_models.append(model)
            
            cache_data = {
                "cached_at": time.time(),
                "models": optimized_models,  # Just array of model ID strings
                "providers": providers_data or {}
            }
            
            # Save without indentation to minimize file size
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, separators=(',', ':'))
            
            with self._lock:
                self.cache_data = cache_data
                
            print(f"✅ Model discovery completed. Found {len(optimized_models)} models total.")
            verbose_print(f"💾 Saved {len(optimized_models)} models to optimized cache")
        except Exception as e:
            verbose_print(f"❌ Error saving model cache: {e}")
    
    def is_cache_valid(self) -> bool:
        """Check if current cache is still valid"""
        with self._lock:
            if not self.cache_data.get("cached_at"):
                return False
            
            cache_age = time.time() - self.cache_data["cached_at"]
            return cache_age <= self.cache_duration
    
    def get_models(self) -> List[str]:
        """Get all cached models (now returns list of model ID strings)"""
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
        Now works with optimized cache format (string array)
        """
        providers_with_model = []
        models = self.get_models()  # Now returns list of model ID strings
        
        # Normalize the requested model for comparison
        requested_normalized = self._normalize_model_name(model_name)
        
        for model_id in models:
            # Extract provider from model_id (supports both "/" and "|" separators)
            provider = "unknown"
            clean_model_id = model_id
            
            if "|" in model_id:
                # New format: "provider|complete_model_name"
                provider, clean_model_id = model_id.split("|", 1)
                # For matching, extract the base model name (part after last /)
                if "/" in clean_model_id:
                    base_model_for_matching = clean_model_id.split("/")[-1]
                else:
                    base_model_for_matching = clean_model_id
            elif "/" in model_id:
                # Old format: "provider/model"
                provider, clean_model_id = model_id.split("/", 1)
                base_model_for_matching = clean_model_id
            else:
                base_model_for_matching = clean_model_id
            
            # Normalize the available model for comparison (use base model name)
            available_normalized = self._normalize_model_name(base_model_for_matching)
            
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
