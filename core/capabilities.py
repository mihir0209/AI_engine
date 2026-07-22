"""
Provider and model capabilities detection and management.
Tracks vision, tool calling, streaming, etc. at BOTH provider and model level.
Loads pre-computed cache from data/capabilities_cache.json for fast startup.
Uses OpenRouter API as source of truth for model vision capabilities.
"""
import json
import os
import logging
import threading
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelCapabilities:
    """Capabilities of a specific model"""
    vision: bool = False
    tool_calling: bool = False
    streaming: bool = True
    embeddings: bool = False
    audio_input: bool = False
    audio_output: bool = False
    image_output: bool = False
    video_input: bool = False
    file_input: bool = False
    max_context_length: int = 4096
    supported_formats: List[str] = field(default_factory=lambda: ["text"])


@dataclass
class ProviderCapabilities:
    """Capabilities of a provider (fallback when model-level unknown)"""
    provider: str
    vision: bool = False
    tool_calling: bool = False
    streaming: bool = True
    embeddings: bool = False
    audio_input: bool = False
    audio_output: bool = False
    image_output: bool = False
    video_input: bool = False
    file_input: bool = False
    max_context_length: int = 4096
    supported_formats: List[str] = field(default_factory=lambda: ["text"])


# ============================================
# MODEL-LEVEL CAPABILITY DATABASE
# ============================================
# Only models that actually support vision are marked vision=True
# If a model is not listed, it's treated as text-only (conservative)

MODEL_CAPABILITIES: Dict[str, Dict[str, ModelCapabilities]] = {
    "gemini": {
        "gemini-2.5-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-2.5-flash-lite": ModelCapabilities(vision=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-2.0-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-2.0-flash-lite": ModelCapabilities(vision=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-1.5-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000, supported_formats=["text", "image"]),
        "gemini-1.5-pro": ModelCapabilities(vision=True, tool_calling=True, max_context_length=2000000, supported_formats=["text", "image"]),
    },
    "groq": {
        "llama-3.3-70b-versatile": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "llama-3.1-8b-instant": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "mixtral-8x7b-32768": ModelCapabilities(max_context_length=32768),
        "gemma2-9b-it": ModelCapabilities(max_context_length=8192),
        "meta-llama/llama-4-scout-17b-16e-instruct": ModelCapabilities(tool_calling=True, max_context_length=131072),
    },
    "nvidia": {
        "nvidia/nemotron-3-nano-30b-a3b": ModelCapabilities(tool_calling=True, max_context_length=4096),
        "meta/llama-3.1-8b-instruct": ModelCapabilities(max_context_length=4096),
        "mistralai/mistral-7b-instruct-v0.3": ModelCapabilities(max_context_length=4096),
    },
    "openrouter": {
        "google/gemini-2.5-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000),
        "meta-llama/llama-4-maverick-17b-128e-instruct": ModelCapabilities(vision=True, tool_calling=True, max_context_length=1000000),
        "openai/gpt-4o-mini": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000),
    },
    "cloudflare": {
        "meta/llama-3.1-8b-instruct-fp8": ModelCapabilities(max_context_length=8192),
        "meta/llama-3-8b-instruct": ModelCapabilities(max_context_length=8192),
    },
    "cerebras": {
        "llama-3.3-70b": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "llama-3.1-8b": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "zai-glm-4.7": ModelCapabilities(max_context_length=128000),
        "gpt-oss-120b": ModelCapabilities(max_context_length=128000),
    },
    "cohere": {
        "command-r-plus": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "command-r": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "command": ModelCapabilities(max_context_length=4096),
    },
    "mistral": {
        "mistral-large-latest": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "mistral-small-latest": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "pixtral-large-latest": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000),
    },
    "kilo": {
        "kilo-auto/free": ModelCapabilities(max_context_length=128000),
        "nvidia/nemotron-ultra-253b-vl": ModelCapabilities(vision=True, max_context_length=131072),
        "google/gemma-4-27b-it-bf16": ModelCapabilities(max_context_length=128000),
    },
    "zai": {
        "glm-4.7-flash": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
        "glm-4.5-flash": ModelCapabilities(vision=True, max_context_length=128000, supported_formats=["text", "image"]),
        "glm-4.6v-flash": ModelCapabilities(vision=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "ollama": {
        "llama3.1": ModelCapabilities(max_context_length=128000),
        "llama3.2": ModelCapabilities(max_context_length=128000),
        "gemma2": ModelCapabilities(max_context_length=8192),
        "qwen2.5": ModelCapabilities(max_context_length=128000),
        "mistral": ModelCapabilities(max_context_length=32768),
        "codellama": ModelCapabilities(max_context_length=16384),
    },
    "github": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
        "gpt-4o-mini": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "vercel": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "huggingface": {
        "meta-llama/Meta-Llama-3.1-70B-Instruct": ModelCapabilities(tool_calling=True, max_context_length=128000),
        "mistralai/Mistral-7B-Instruct-v0.3": ModelCapabilities(max_context_length=32768),
    },
    "opencode_zen": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "hcnsec": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "mimo": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "paxsenix": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "freetheai": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "hermes": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "pollinations": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
    "longcat": {
        "gpt-4o": ModelCapabilities(vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    },
}

# ============================================
# PROVIDER-LEVEL FALLBACKS
# ============================================
PROVIDER_CAPABILITIES: Dict[str, ProviderCapabilities] = {
    "gemini": ProviderCapabilities(provider="gemini", vision=True, tool_calling=True, max_context_length=1000000, supported_formats=["text", "image"]),
    "groq": ProviderCapabilities(provider="groq", vision=False, tool_calling=True, max_context_length=128000, supported_formats=["text"]),
    "nvidia": ProviderCapabilities(provider="nvidia", vision=False, tool_calling=True, max_context_length=4096, supported_formats=["text"]),
    "openrouter": ProviderCapabilities(provider="openrouter", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "cloudflare": ProviderCapabilities(provider="cloudflare", vision=False, max_context_length=8192, supported_formats=["text"]),
    "cerebras": ProviderCapabilities(provider="cerebras", vision=False, tool_calling=True, max_context_length=128000, supported_formats=["text"]),
    "cohere": ProviderCapabilities(provider="cohere", vision=False, tool_calling=True, max_context_length=128000, supported_formats=["text"]),
    "mistral": ProviderCapabilities(provider="mistral", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "huggingface": ProviderCapabilities(provider="huggingface", vision=False, tool_calling=True, max_context_length=128000, supported_formats=["text"]),
    "kilo": ProviderCapabilities(provider="kilo", vision=True, max_context_length=128000, supported_formats=["text", "image"]),
    "github": ProviderCapabilities(provider="github", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "vercel": ProviderCapabilities(provider="vercel", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "opencode_zen": ProviderCapabilities(provider="opencode_zen", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "pollinations": ProviderCapabilities(provider="pollinations", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "hermes": ProviderCapabilities(provider="hermes", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "longcat": ProviderCapabilities(provider="longcat", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "zai": ProviderCapabilities(provider="zai", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "hcnsec": ProviderCapabilities(provider="hcnsec", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "mimo": ProviderCapabilities(provider="mimo", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "paxsenix": ProviderCapabilities(provider="paxsenix", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "freetheai": ProviderCapabilities(provider="freetheai", vision=True, tool_calling=True, max_context_length=128000, supported_formats=["text", "image"]),
    "ollama": ProviderCapabilities(provider="ollama", vision=False, max_context_length=128000, supported_formats=["text"]),
    "llm7": ProviderCapabilities(provider="llm7", vision=False, max_context_length=4096, supported_formats=["text"]),
    "g4f_groq": ProviderCapabilities(provider="g4f_groq", vision=False, max_context_length=128000, supported_formats=["text"]),
    "g4f_gemini": ProviderCapabilities(provider="g4f_gemini", vision=True, max_context_length=1000000, supported_formats=["text", "image"]),
    "g4f_ollama": ProviderCapabilities(provider="g4f_ollama", vision=False, max_context_length=4096, supported_formats=["text"]),
    "g4f_pollinations": ProviderCapabilities(provider="g4f_pollinations", vision=False, max_context_length=4096, supported_formats=["text"]),
    "g4f_nvidia": ProviderCapabilities(provider="g4f_nvidia", vision=False, max_context_length=4096, supported_formats=["text"]),
}


class CapabilityManager:
    """Manages provider and model capabilities with vision detection"""

    def __init__(self):
        self.model_caps: Dict[str, Dict[str, ModelCapabilities]] = dict(MODEL_CAPABILITIES)
        self.provider_caps: Dict[str, ProviderCapabilities] = dict(PROVIDER_CAPABILITIES)
        self.custom_caps: Dict[str, ProviderCapabilities] = {}
        self._cache = self._load_cache()
        self._openrouter_vision: Set[str] = set()
        self._openrouter_tool: Set[str] = set()
        self._openrouter_image_output: Set[str] = set()
        self._openrouter_audio_input: Set[str] = set()
        self._openrouter_audio_output: Set[str] = set()
        self._openrouter_video_input: Set[str] = set()
        self._openrouter_file_input: Set[str] = set()
        self._openrouter_loaded = False
        self._openrouter_lock = threading.Lock()
        self._load_openrouter_cache()

    def _load_cache(self) -> Dict:
        """Load pre-computed capabilities cache"""
        cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'capabilities_cache.json')
        if os.path.exists(cache_path):
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _load_openrouter_cache(self):
        """Load OpenRouter capabilities from local cache file"""
        cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'openrouter_capabilities.json')
        if os.path.exists(cache_path):
            try:
                with open(cache_path) as f:
                    data = json.load(f)
                self._openrouter_vision = set(data.get('vision_models', []))
                self._openrouter_tool = set(data.get('tool_models', []))
                self._openrouter_image_output = set(data.get('image_output_models', []))
                self._openrouter_audio_input = set(data.get('audio_input_models', []))
                self._openrouter_audio_output = set(data.get('audio_output_models', []))
                self._openrouter_video_input = set(data.get('video_input_models', []))
                self._openrouter_file_input = set(data.get('file_input_models', []))
                ts = data.get('timestamp', 0)
                if time.time() - ts < 86400:
                    self._openrouter_loaded = True
                    return
            except (json.JSONDecodeError, OSError):
                pass

    def _save_openrouter_cache(self):
        """Save OpenRouter capabilities to local cache file"""
        cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'openrouter_capabilities.json')
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump({
                'vision_models': sorted(self._openrouter_vision),
                'tool_models': sorted(self._openrouter_tool),
                'image_output_models': sorted(self._openrouter_image_output),
                'audio_input_models': sorted(self._openrouter_audio_input),
                'audio_output_models': sorted(self._openrouter_audio_output),
                'video_input_models': sorted(self._openrouter_video_input),
                'file_input_models': sorted(self._openrouter_file_input),
                'timestamp': time.time(),
            }, f)

    def fetch_openrouter_capabilities(self) -> bool:
        """Fetch model capabilities from OpenRouter API and cache locally.
        Returns True if successful.
        """
        if self._openrouter_loaded:
            return True
        with self._openrouter_lock:
            if self._openrouter_loaded:
                return True
            try:
                import requests
                resp = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"OpenRouter API returned {resp.status_code}")
                    return False
                data = resp.json()
                models = data.get('data', [])
                vision = set()
                tool = set()
                image_output = set()
                audio_input = set()
                audio_output = set()
                video_input = set()
                file_input = set()
                for m in models:
                    mid = m.get('id', '')
                    mid_lower = mid.lower()
                    arch = m.get('architecture', {})
                    input_mods = arch.get('input_modalities', [])
                    output_mods = arch.get('output_modalities', [])
                    params = m.get('supported_parameters', [])
                    if 'image' in input_mods:
                        vision.add(mid_lower)
                    if 'image' in output_mods:
                        image_output.add(mid_lower)
                    if 'audio' in input_mods:
                        audio_input.add(mid_lower)
                    if 'audio' in output_mods:
                        audio_output.add(mid_lower)
                    if 'video' in input_mods:
                        video_input.add(mid_lower)
                    if 'file' in input_mods:
                        file_input.add(mid_lower)
                    if 'tools' in params:
                        tool.add(mid_lower)
                self._openrouter_vision = vision
                self._openrouter_tool = tool
                self._openrouter_image_output = image_output
                self._openrouter_audio_input = audio_input
                self._openrouter_audio_output = audio_output
                self._openrouter_video_input = video_input
                self._openrouter_file_input = file_input
                self._openrouter_loaded = True
                self._save_openrouter_cache()
                logger.info(f"OpenRouter capabilities: {len(vision)} vision, {len(image_output)} image-gen, {len(audio_output)} audio-gen, {len(video_input)} video, {len(file_input)} file, {len(tool)} tools")
                return True
            except Exception as e:
                logger.warning(f"Failed to fetch OpenRouter capabilities: {e}")
                return False

    def _openrouter_supports_vision(self, model: str) -> Optional[bool]:
        """Check if a model supports vision using OpenRouter data.
        Returns True/False if found, None if unknown.
        """
        if not model or not self._openrouter_vision:
            return None
        model_lower = model.lower()
        if model_lower in self._openrouter_vision:
            return True
        if '/' in model_lower:
            short = model_lower.split('/', 1)[1]
            if short in self._openrouter_vision:
                return True
        for mid in self._openrouter_vision:
            if mid.endswith('/' + model_lower) or mid.endswith('/' + model_lower.split('/')[-1]):
                return True
        if model_lower in self._openrouter_tool:
            return False
        for mid in self._openrouter_tool:
            if mid.endswith('/' + model_lower) or mid.endswith('/' + model_lower.split('/')[-1]):
                return False
        return None

    def _openrouter_supports_tool(self, model: str) -> Optional[bool]:
        """Check if a model supports tool calling using OpenRouter data."""
        if not model or not self._openrouter_tool:
            return None
        model_lower = model.lower()
        if model_lower in self._openrouter_tool:
            return True
        if '/' in model_lower:
            short = model_lower.split('/', 1)[1]
            if short in self._openrouter_tool:
                return True
        for mid in self._openrouter_tool:
            if mid.endswith('/' + model_lower) or mid.endswith('/' + model_lower.split('/')[-1]):
                return True
        return None

    def _openrouter_in_set(self, model: str, modality_set: Set[str]) -> bool:
        """Generic check: does model exist in the given OpenRouter modality set?"""
        if not model or not modality_set:
            return False
        model_lower = model.lower()
        if model_lower in modality_set:
            return True
        if '/' in model_lower:
            short = model_lower.split('/', 1)[1]
            if short in modality_set:
                return True
        for mid in modality_set:
            if mid.endswith('/' + model_lower) or mid.endswith('/' + model_lower.split('/')[-1]):
                return True
        return False

    def supports_image_generation(self, model: str = None) -> bool:
        """Check if a model can generate images (output modality includes image)"""
        if model:
            if self._openrouter_in_set(model, self._openrouter_image_output):
                return True
        return False

    def supports_audio_input(self, model: str = None) -> bool:
        """Check if a model can accept audio input"""
        if model:
            if self._openrouter_in_set(model, self._openrouter_audio_input):
                return True
        return False

    def supports_audio_output(self, model: str = None) -> bool:
        """Check if a model can produce audio output"""
        if model:
            if self._openrouter_in_set(model, self._openrouter_audio_output):
                return True
        return False

    def supports_video_input(self, model: str = None) -> bool:
        """Check if a model can accept video input"""
        if model:
            if self._openrouter_in_set(model, self._openrouter_video_input):
                return True
        return False

    def supports_file_input(self, model: str = None) -> bool:
        """Check if a model can accept file input"""
        if model:
            if self._openrouter_in_set(model, self._openrouter_file_input):
                return True
        return False

    def get_modality_summary(self) -> Dict:
        """Get counts of all modality categories from OpenRouter data"""
        return {
            "vision": len(self._openrouter_vision),
            "image_generation": len(self._openrouter_image_output),
            "audio_input": len(self._openrouter_audio_input),
            "audio_output": len(self._openrouter_audio_output),
            "video_input": len(self._openrouter_video_input),
            "file_input": len(self._openrouter_file_input),
            "tool_calling": len(self._openrouter_tool),
            "loaded": self._openrouter_loaded,
        }

    def get_models_for_modality(self, modality: str) -> List[str]:
        """Get model IDs for a specific modality. Supported: vision, image_gen, audio_in, audio_out, video, file, tools"""
        modality_map = {
            'vision': self._openrouter_vision,
            'image_gen': self._openrouter_image_output,
            'audio_in': self._openrouter_audio_input,
            'audio_out': self._openrouter_audio_output,
            'video': self._openrouter_video_input,
            'file': self._openrouter_file_input,
            'tools': self._openrouter_tool,
        }
        return sorted(modality_map.get(modality, set()))

    def _rebuild_cache(self):
        """Rebuild and save the capabilities cache"""
        cache = {
            'vision_providers': self.get_vision_providers(),
            'provider_capabilities': {},
            'model_capabilities': {},
            'image_compatibility': {},
        }
        for name, caps in self.provider_caps.items():
            cache['provider_capabilities'][name] = {
                'vision': caps.vision, 'tool_calling': caps.tool_calling,
                'streaming': caps.streaming, 'max_context_length': caps.max_context_length,
                'supported_formats': caps.supported_formats,
            }
        for provider, models in self.model_caps.items():
            for model_name, caps in models.items():
                cache['model_capabilities'][f'{provider}/{model_name}'] = {
                    'vision': caps.vision, 'tool_calling': caps.tool_calling,
                    'streaming': caps.streaming, 'max_context_length': caps.max_context_length,
                    'supported_formats': caps.supported_formats,
                }
        cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'capabilities_cache.json')
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(cache, f, indent=2)
        self._cache = cache

    def get_model_capabilities(self, provider: str, model: str) -> Optional[ModelCapabilities]:
        """Get capabilities for a specific model under a provider"""
        provider_models = self.model_caps.get(provider, {})
        if model in provider_models:
            return provider_models[model]
        for pattern, caps in provider_models.items():
            if model and pattern in model:
                return caps
        return None

    def get_provider_capabilities(self, provider: str) -> Optional[ProviderCapabilities]:
        """Get provider-level capabilities (fallback)"""
        return self.custom_caps.get(provider) or self.provider_caps.get(provider)

    def supports_vision(self, provider: str, model: str = None) -> bool:
        """Check if a provider/model supports vision/image input.

        Priority: model database > OpenRouter data > fuzzy keywords > provider fallback.
        """
        if model:
            # 1. Check exact model database
            model_caps = self.get_model_capabilities(provider, model)
            if model_caps:
                return model_caps.vision

            # 2. Check OpenRouter data (authoritative source)
            or_vision = self._openrouter_supports_vision(model)
            if or_vision is not None:
                return or_vision

            # 3. Fuzzy match on model name keywords
            vision_keywords = [
                "vl", "vision", "vlm", "multimodal", "image", "visual",
                "clip", "img", "pixtral", "fuyu",
            ]
            model_lower = model.lower()
            for kw in vision_keywords:
                if kw in model_lower:
                    return True

        provider_caps = self.get_provider_capabilities(provider)
        return provider_caps.vision if provider_caps else False

    def get_vision_model_for_provider(self, provider: str) -> Optional[str]:
        """Get the best vision model for a provider, using OpenRouter data as source of truth."""
        # First check our static database
        prov_models = self.model_caps.get(provider, {})
        for model_name, caps in prov_models.items():
            if caps.vision:
                return model_name

        # If OpenRouter loaded, try to match provider prefix to find vision models
        if self._openrouter_loaded and self._openrouter_vision:
            # Map provider name to OpenRouter prefixes
            prefix_map = {
                'g4f_gemini': ['google/'],
                'g4f_nvidia': ['nvidia/'],
                'g4f_groq': ['meta-llama/', 'groq/'],
                'gemini': ['google/'],
                'github': ['meta-llama/', 'openai/', 'google/'],
                'kilo': ['nvidia/', 'google/'],
            }
            prefixes = prefix_map.get(provider, [f'{provider}/'])
            # Prefer stable model names (no preview/tts/audio suffixes)
            stable_suffixes = ('-preview', '-tts', '-native-audio', '-image-preview')
            for mid in sorted(self._openrouter_vision):
                for prefix in prefixes:
                    if mid.startswith(prefix):
                        model_name = mid.split('/', 1)[1] if '/' in mid else mid
                        if not any(model_name.endswith(s) for s in stable_suffixes):
                            return model_name
            # Fallback: return any matching model including preview
            for mid in sorted(self._openrouter_vision):
                for prefix in prefixes:
                    if mid.startswith(prefix):
                        model_name = mid.split('/', 1)[1] if '/' in mid else mid
                        return model_name
        return None

    def get_any_vision_model(self) -> Optional[str]:
        """Get any known vision model name that most providers support.
        Returns base model name (without provider prefix) for compatibility.
        """
        preferred = [
            ("gemini-2.5-flash", "google/gemini-2.5-flash"),
            ("gemini-2.0-flash", "google/gemini-2.0-flash"),
            ("gpt-4o", "openai/gpt-4o"),
            ("gpt-4o-mini", "openai/gpt-4o-mini"),
        ]
        for base_name, or_id in preferred:
            if or_id.lower() in self._openrouter_vision:
                return base_name
        if self._openrouter_vision:
            first = next(iter(self._openrouter_vision))
            return first.split('/', 1)[1] if '/' in first else first
        return None

    def supports_tool_calling(self, provider: str, model: str = None) -> bool:
        if model:
            model_caps = self.get_model_capabilities(provider, model)
            if model_caps:
                return model_caps.tool_calling
            or_tool = self._openrouter_supports_tool(model)
            if or_tool is not None:
                return or_tool
        provider_caps = self.get_provider_capabilities(provider)
        return provider_caps.tool_calling if provider_caps else False

    def get_max_context(self, provider: str, model: str = None) -> int:
        if model:
            model_caps = self.get_model_capabilities(provider, model)
            if model_caps:
                return model_caps.max_context_length
        provider_caps = self.get_provider_capabilities(provider)
        return provider_caps.max_context_length if provider_caps else 4096

    def get_vision_providers(self) -> List[str]:
        """Get all providers that support vision AND are enabled, sorted by priority (lowest = best)"""
        try:
            from config import AI_CONFIGS
        except ImportError:
            try:
                from core.config import AI_CONFIGS
            except ImportError:
                AI_CONFIGS = {}
        providers = []
        for name, caps in self.provider_caps.items():
            if caps.vision and name in AI_CONFIGS and AI_CONFIGS[name].get('enabled', True):
                providers.append((name, AI_CONFIGS[name].get("priority", 999)))
        providers.sort(key=lambda x: x[1])
        return [name for name, _ in providers]

    def get_all_capabilities(self) -> Dict[str, Dict]:
        """Get all provider capabilities"""
        return {
            name: {
                "vision": caps.vision,
                "tool_calling": caps.tool_calling,
                "streaming": caps.streaming,
                "max_context_length": caps.max_context_length,
                "supported_formats": caps.supported_formats,
            }
            for name, caps in self.provider_caps.items()
        }

    def get_model_list(self) -> List[Dict]:
        """Get all known models with their capabilities"""
        result = []
        for provider, models in self.model_caps.items():
            for model_name, caps in models.items():
                result.append({
                    "provider": provider,
                    "model": model_name,
                    "vision": caps.vision,
                    "tool_calling": caps.tool_calling,
                    "max_context_length": caps.max_context_length,
                })
        return result

    def check_image_compatibility(self, provider: str, model: str = None) -> Dict:
        """Check if a provider/model can handle image uploads.
        When model is None/default, always return compatible — autodecide handles vision routing.
        Returns: {compatible: bool, reason: str, suggestions: list}
        """
        # If no specific model, always compatible (autodecide will route to vision provider)
        if not model or model in ("auto", "default", ""):
            return {"compatible": True, "reason": "Model is auto/default — autodecide will route to vision provider", "suggestions": []}

        vision_ok = self.supports_vision(provider, model)

        if vision_ok:
            return {"compatible": True, "reason": "Model supports vision", "suggestions": []}

        # Find vision providers with their best models
        suggestions = []
        for prov_name, prov_caps in self.provider_caps.items():
            if prov_caps.vision:
                best_model = None
                prov_models = self.model_caps.get(prov_name, {})
                for model_name, caps in prov_models.items():
                    if caps.vision:
                        best_model = model_name
                        break
                if best_model:
                    suggestions.append(f"{prov_name} ({best_model})")
                else:
                    suggestions.append(prov_name)

        return {
            "compatible": False,
            "reason": f"'{provider}' with model '{model}' does not support image input",
            "suggestions": suggestions[:5],
        }


class ErrorMessageManager:
    """Manages user-friendly error messages"""

    ERROR_MESSAGES = {
        "rate_limit": {"message": "Rate limit exceeded. Please wait before retrying.", "suggestion": "Try a different provider or wait a few minutes.", "code": "RATE_LIMIT_EXCEEDED"},
        "auth_error": {"message": "Authentication failed. Invalid or missing API key.", "suggestion": "Check your API key configuration in .env file.", "code": "AUTH_FAILED"},
        "quota_exceeded": {"message": "Daily quota exceeded for this provider.", "suggestion": "Try a different provider or wait until quota resets.", "code": "QUOTA_EXCEEDED"},
        "service_unavailable": {"message": "Provider service is currently unavailable.", "suggestion": "Try again later or use a different provider.", "code": "SERVICE_UNAVAILABLE"},
        "timeout": {"message": "Request timed out.", "suggestion": "Try a shorter prompt or use a faster provider.", "code": "TIMEOUT"},
        "empty_response": {"message": "Provider returned an empty response.", "suggestion": "Try rephrasing your message.", "code": "EMPTY_RESPONSE"},
        "model_not_found": {"message": "Requested model not found.", "suggestion": "Check available models with GET /v1/models.", "code": "MODEL_NOT_FOUND"},
        "no_providers": {"message": "No providers available.", "suggestion": "Configure at least one provider in config.py.", "code": "NO_PROVIDERS"},
        "no_vision_support": {"message": "This model does not support image input.", "suggestion": "Switch to a vision-capable provider (Gemini, OpenRouter, Mistral).", "code": "NO_VISION_SUPPORT"},
        "provider_not_found": {"message": "Provider not found.", "suggestion": "Check available providers with GET /api/providers.", "code": "PROVIDER_NOT_FOUND"},
        "chat_not_found": {"message": "Chat not found.", "suggestion": "Check the chat ID or create a new chat.", "code": "CHAT_NOT_FOUND"},
        "message_not_found": {"message": "Message not found.", "suggestion": "Check the message ID.", "code": "MESSAGE_NOT_FOUND"},
        "file_too_large": {"message": "File exceeds maximum size limit (10MB).", "suggestion": "Compress or split the file.", "code": "FILE_TOO_LARGE"},
        "invalid_file_type": {"message": "File type not supported.", "suggestion": "Use supported formats: .txt, .md, .json, .py, .js, .ts, .html, .css, .yaml, .png, .jpg", "code": "INVALID_FILE_TYPE"},
        "circuit_open": {"message": "Service temporarily unavailable due to repeated failures.", "suggestion": "Wait a moment and try again.", "code": "CIRCUIT_OPEN"},
    }

    @classmethod
    def get_error(cls, error_type: str, details: str = None) -> Dict:
        error_info = cls.ERROR_MESSAGES.get(error_type, {"message": f"Unknown error: {error_type}", "suggestion": "Please try again or contact support.", "code": "UNKNOWN_ERROR"})
        result = dict(error_info)
        if details:
            result["details"] = details
        return result

    @classmethod
    def get_all_errors(cls) -> Dict:
        return cls.ERROR_MESSAGES


capability_manager = CapabilityManager()
error_message_manager = ErrorMessageManager()
