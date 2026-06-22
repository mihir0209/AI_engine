"""Tests for plugin system"""
import pytest
import tempfile
import shutil


@pytest.fixture
def plugin_manager():
    from core.plugin_system import PluginManager
    temp_dir = tempfile.mkdtemp()
    manager = PluginManager(plugins_dir=temp_dir)
    yield manager
    shutil.rmtree(temp_dir)


def test_register_hook(plugin_manager):
    def my_callback(**kwargs):
        return "result"

    plugin_manager.register_hook("test_hook", my_callback)
    assert "test_hook" in plugin_manager.hooks


def test_trigger_hook(plugin_manager):
    results = []

    def callback1(**kwargs):
        results.append("c1")
        return "r1"

    def callback2(**kwargs):
        results.append("c2")
        return "r2"

    plugin_manager.register_hook("test", callback1)
    plugin_manager.register_hook("test", callback2)

    hook_results = plugin_manager.trigger_hook("test", data="test")
    assert len(hook_results) == 2
    assert "c1" in results
    assert "c2" in results


def test_trigger_hook_empty(plugin_manager):
    results = plugin_manager.trigger_hook("nonexistent")
    assert results == []


def test_list_plugins_empty(plugin_manager):
    plugins = plugin_manager.list_plugins()
    assert len(plugins) == 0


def test_enable_disable_plugin(plugin_manager):
    from core.plugin_system import Plugin, PluginManifest
    from unittest.mock import MagicMock

    manifest = PluginManifest(name="test", version="1.0", description="Test", author="Test")
    module = MagicMock()
    plugin = Plugin(manifest=manifest, module=module)
    plugin_manager.plugins["test"] = plugin

    plugin_manager.disable_plugin("test")
    assert plugin_manager.plugins["test"].manifest.enabled is False

    plugin_manager.enable_plugin("test")
    assert plugin_manager.plugins["test"].manifest.enabled is True


def test_get_plugin_config(plugin_manager):
    from core.plugin_system import Plugin, PluginManifest
    from unittest.mock import MagicMock

    manifest = PluginManifest(name="test", version="1.0", description="Test", author="Test", config={"key": "value"})
    plugin = Plugin(manifest=manifest, module=MagicMock())
    plugin_manager.plugins["test"] = plugin

    config = plugin_manager.get_plugin_config("test")
    assert config["key"] == "value"


def test_set_plugin_config(plugin_manager):
    from core.plugin_system import Plugin, PluginManifest
    from unittest.mock import MagicMock

    manifest = PluginManifest(name="test", version="1.0", description="Test", author="Test", config={})
    plugin = Plugin(manifest=manifest, module=MagicMock())
    plugin_manager.plugins["test"] = plugin

    plugin_manager.set_plugin_config("test", {"new_key": "new_value"})
    assert plugin_manager.plugins["test"].manifest.config["new_key"] == "new_value"
