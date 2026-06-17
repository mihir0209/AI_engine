"""
Plugin system for AI Engine
Provides plugin architecture, loading, and management
"""
import os
import json
import importlib.util
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class PluginManifest:
    """Plugin manifest/metadata"""
    name: str
    version: str
    description: str
    author: str
    enabled: bool = True
    hooks: List[str] = field(default_factory=list)  # Event hooks this plugin listens to
    dependencies: List[str] = field(default_factory=list)  # Other plugins required
    config: Dict[str, Any] = field(default_factory=dict)  # Plugin-specific config


@dataclass
class Plugin:
    """Loaded plugin instance"""
    manifest: PluginManifest
    module: Any  # The loaded Python module
    instance: Any = None  # Plugin instance if it has a Plugin class
    loaded_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "loaded"  # loaded, active, error, disabled


class PluginManager:
    """Manages plugin lifecycle"""
    
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(exist_ok=True)
        self.plugins: Dict[str, Plugin] = {}
        self.hooks: Dict[str, List[Callable]] = {}  # hook_name -> [callback_functions]
        self._load_plugins()
    
    def _load_plugins(self):
        """Load all plugins from plugins directory"""
        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir():
                manifest_file = plugin_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        self._load_plugin(plugin_dir)
                    except Exception as e:
                        logger.error(f"Failed to load plugin {plugin_dir.name}: {e}")
    
    def _load_plugin(self, plugin_path: Path):
        """Load a single plugin"""
        # Read manifest
        manifest_file = plugin_path / "manifest.json"
        with open(manifest_file, "r") as f:
            manifest_data = json.load(f)
        
        manifest = PluginManifest(**manifest_data)
        
        # Load main module
        main_file = plugin_path / "main.py"
        if not main_file.exists():
            logger.warning(f"Plugin {manifest.name} has no main.py")
            return
        
        spec = importlib.util.spec_from_file_location(
            f"plugins.{manifest.name}",
            str(main_file)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Create plugin instance if Plugin class exists
        instance = None
        if hasattr(module, "Plugin"):
            plugin_class = getattr(module, "Plugin")
            instance = plugin_class()
        
        # Register hooks
        if instance and hasattr(instance, "get_hooks"):
            hooks = instance.get_hooks()
            for hook_name, callback in hooks.items():
                self.register_hook(hook_name, callback)
        
        plugin = Plugin(
            manifest=manifest,
            module=module,
            instance=instance
        )
        
        self.plugins[manifest.name] = plugin
        logger.info(f"Loaded plugin: {manifest.name} v{manifest.version}")
    
    def register_hook(self, hook_name: str, callback: Callable):
        """Register a callback for a hook"""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(callback)
    
    def trigger_hook(self, hook_name: str, **kwargs) -> List[Any]:
        """Trigger all callbacks for a hook"""
        results = []
        for callback in self.hooks.get(hook_name, []):
            try:
                result = callback(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in hook {hook_name}: {e}")
        return results
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].manifest.enabled = True
            self.plugins[plugin_name].status = "active"
            return True
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].manifest.enabled = False
            self.plugins[plugin_name].status = "disabled"
            return True
        return False
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """Get plugin by name"""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> List[Dict]:
        """List all plugins with status"""
        return [
            {
                "name": p.manifest.name,
                "version": p.manifest.version,
                "description": p.manifest.description,
                "author": p.manifest.author,
                "enabled": p.manifest.enabled,
                "status": p.status,
                "hooks": p.manifest.hooks
            }
            for p in self.plugins.values()
        ]
    
    def get_plugin_config(self, plugin_name: str) -> Dict:
        """Get plugin configuration"""
        plugin = self.plugins.get(plugin_name)
        if plugin:
            return plugin.manifest.config
        return {}
    
    def set_plugin_config(self, plugin_name: str, config: Dict):
        """Update plugin configuration"""
        plugin = self.plugins.get(plugin_name)
        if plugin:
            plugin.manifest.config.update(config)
            # Save to manifest file
            manifest_file = self.plugins_dir / plugin_name / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, "r") as f:
                    data = json.load(f)
                data["config"] = plugin.manifest.config
                with open(manifest_file, "w") as f:
                    json.dump(data, f, indent=2)


# Built-in hooks
BUILTIN_HOOKS = [
    "before_request",      # Before making AI request
    "after_request",       # After AI response received
    "before_chat_message", # Before processing chat message
    "after_chat_message",  # After chat message processed
    "on_error",           # On error occurred
    "on_provider_change", # When provider changes
]


# Global instance
plugin_manager = PluginManager()
