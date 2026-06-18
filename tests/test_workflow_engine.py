"""Tests for workflow engine"""
import pytest
import tempfile
import shutil


@pytest.fixture
def workflow_engine():
    from workflow_engine import WorkflowEngine
    temp_dir = tempfile.mkdtemp()
    engine = WorkflowEngine(data_dir=temp_dir)
    yield engine
    shutil.rmtree(temp_dir)


def test_create_workflow(workflow_engine):
    steps = [
        {"id": "s1", "name": "Step 1", "step_type": "ai_call", "next_step": "s2"},
        {"id": "s2", "name": "Step 2", "step_type": "output"}
    ]
    wf = workflow_engine.create_workflow("Test WF", "Description", steps)
    assert wf.id.startswith("wf_")
    assert wf.name == "Test WF"
    assert len(wf.steps) == 2


def test_get_workflow(workflow_engine):
    steps = [{"id": "s1", "step_type": "ai_call"}]
    wf = workflow_engine.create_workflow("Test", "Desc", steps)
    retrieved = workflow_engine.get_workflow(wf.id)
    assert retrieved is not None
    assert retrieved.name == "Test"


def test_list_workflows(workflow_engine):
    steps = [{"id": "s1", "step_type": "ai_call"}]
    workflow_engine.create_workflow("WF1", "Desc1", steps)
    workflow_engine.create_workflow("WF2", "Desc2", steps)
    
    wfs = workflow_engine.list_workflows()
    assert len(wfs) == 2


def test_execute_simple_workflow(workflow_engine):
    steps = [
        {"id": "start", "name": "Start", "step_type": "ai_call", "next_step": "end"},
        {"id": "end", "name": "End", "step_type": "output", "config": {"field": "result"}}
    ]
    wf = workflow_engine.create_workflow("Simple", "Test", steps)
    exec = workflow_engine.execute_workflow(wf.id, {"input": "test"})
    assert exec.status == "completed"


def test_execute_conditional_workflow(workflow_engine):
    steps = [
        {"id": "check", "step_type": "condition", 
         "config": {"type": "equals", "value": "yes", "compare_to": "yes"},
         "on_true": "success", "on_false": "fail"},
        {"id": "success", "step_type": "output", "next_step": None},
        {"id": "fail", "step_type": "output", "next_step": None}
    ]
    wf = workflow_engine.create_workflow("Cond", "Test", steps)
    exec = workflow_engine.execute_workflow(wf.id, {})
    assert exec.status == "completed"
    assert "check" in exec.step_results


def test_execute_not_found(workflow_engine):
    with pytest.raises(ValueError):
        workflow_engine.execute_workflow("nonexistent", {})


def test_get_execution(workflow_engine):
    steps = [{"id": "s1", "step_type": "output"}]
    wf = workflow_engine.create_workflow("Test", "Desc", steps)
    exec = workflow_engine.execute_workflow(wf.id, {})
    retrieved = workflow_engine.get_execution(exec.id)
    assert retrieved is not None


def test_workflow_with_loop(workflow_engine):
    steps = [
        {"id": "init", "step_type": "ai_call", "next_step": "process"},
        {"id": "process", "step_type": "transform", "config": {"type": "extract", "field": "input"}, "next_step": "output"},
        {"id": "output", "step_type": "output"}
    ]
    wf = workflow_engine.create_workflow("Loop Test", "Test", steps)
    exec = workflow_engine.execute_workflow(wf.id, {"input": "test_data"})
    assert exec.status == "completed"
