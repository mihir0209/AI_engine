"""Tests for plugin system and workflow engine"""
import pytest
import tempfile
import shutil


# === Plugin System Tests ===

@pytest.fixture
def plugin_manager():
    from core.plugin_system import PluginManager
    temp_dir = tempfile.mkdtemp()
    manager = PluginManager(plugins_dir=temp_dir)
    yield manager
    shutil.rmtree(temp_dir)


def test_plugin_manager_init(plugin_manager):
    assert plugin_manager.plugins_dir.exists()
    assert len(plugin_manager.plugins) == 0


def test_register_hook(plugin_manager):
    def my_callback(**kwargs):
        return "test_result"

    plugin_manager.register_hook("test_hook", my_callback)
    assert "test_hook" in plugin_manager.hooks


def test_trigger_hook(plugin_manager):
    results = []

    def callback1(**kwargs):
        results.append("callback1")
        return "result1"

    def callback2(**kwargs):
        results.append("callback2")
        return "result2"

    plugin_manager.register_hook("test_hook", callback1)
    plugin_manager.register_hook("test_hook", callback2)

    hook_results = plugin_manager.trigger_hook("test_hook", data="test")
    assert len(hook_results) == 2
    assert "callback1" in results
    assert "callback2" in results


def test_list_plugins_empty(plugin_manager):
    plugins = plugin_manager.list_plugins()
    assert len(plugins) == 0


# === Workflow Engine Tests ===

@pytest.fixture
def workflow_engine():
    from core.workflow_engine import WorkflowEngine
    temp_dir = tempfile.mkdtemp()
    engine = WorkflowEngine(data_dir=temp_dir)
    yield engine
    shutil.rmtree(temp_dir)


def test_create_workflow(workflow_engine):
    steps = [
        {"id": "step1", "name": "First Step", "step_type": "ai_call", "next_step": "step2"},
        {"id": "step2", "name": "Second Step", "step_type": "transform"}
    ]

    workflow = workflow_engine.create_workflow("Test Workflow", "A test workflow", steps)
    assert workflow.id.startswith("wf_")
    assert workflow.name == "Test Workflow"
    assert len(workflow.steps) == 2


def test_get_workflow(workflow_engine):
    steps = [{"id": "step1", "step_type": "ai_call"}]
    workflow = workflow_engine.create_workflow("Test", "Description", steps)

    retrieved = workflow_engine.get_workflow(workflow.id)
    assert retrieved is not None
    assert retrieved.name == "Test"


def test_list_workflows(workflow_engine):
    steps = [{"id": "step1", "step_type": "ai_call"}]
    workflow_engine.create_workflow("Workflow 1", "Desc 1", steps)
    workflow_engine.create_workflow("Workflow 2", "Desc 2", steps)

    workflows = workflow_engine.list_workflows()
    assert len(workflows) == 2


def test_execute_workflow_simple(workflow_engine):
    steps = [
        {"id": "start", "name": "Start", "step_type": "ai_call", "next_step": "end"},
        {"id": "end", "name": "End", "step_type": "output", "config": {"field": "result"}}
    ]

    workflow = workflow_engine.create_workflow("Simple WF", "Simple workflow", steps)
    execution = workflow_engine.execute_workflow(workflow.id, {"input": "test"})

    assert execution.status == "completed"
    assert execution.completed_at is not None


def test_execute_workflow_with_condition(workflow_engine):
    steps = [
        {"id": "check", "name": "Check", "step_type": "condition",
         "config": {"type": "equals", "value": "yes", "compare_to": "yes"},
         "on_true": "success", "on_false": "fail"},
        {"id": "success", "name": "Success", "step_type": "output", "next_step": None},
        {"id": "fail", "name": "Fail", "step_type": "output", "next_step": None}
    ]

    workflow = workflow_engine.create_workflow("Conditional WF", "Workflow with condition", steps)
    execution = workflow_engine.execute_workflow(workflow.id, {})

    assert execution.status == "completed"
    assert "check" in execution.step_results


def test_execute_workflow_not_found(workflow_engine):
    with pytest.raises(ValueError):
        workflow_engine.execute_workflow("nonexistent", {})


def test_get_execution(workflow_engine):
    steps = [{"id": "step1", "step_type": "output"}]
    workflow = workflow_engine.create_workflow("Test", "Desc", steps)
    execution = workflow_engine.execute_workflow(workflow.id, {})

    retrieved = workflow_engine.get_execution(execution.id)
    assert retrieved is not None
    assert retrieved.id == execution.id
