"""
Workflow engine for AI Engine
Provides multi-step pipelines and conditional routing
"""
import json
import os
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class StepType(Enum):
    """Workflow step types"""
    AI_CALL = "ai_call"
    TRANSFORM = "transform"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"
    OUTPUT = "output"


@dataclass
class WorkflowStep:
    """A single step in a workflow"""
    id: str
    name: str
    step_type: StepType
    config: Dict[str, Any] = field(default_factory=dict)
    next_step: Optional[str] = None  # Default next step
    on_true: Optional[str] = None    # For conditionals
    on_false: Optional[str] = None   # For conditionals
    error_handler: Optional[str] = None


@dataclass
class Workflow:
    """A complete workflow definition"""
    id: str
    name: str
    description: str
    steps: Dict[str, WorkflowStep]
    start_step: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0.0"
    enabled: bool = True


@dataclass
class WorkflowExecution:
    """Execution instance of a workflow"""
    id: str
    workflow_id: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    current_step: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    step_results: Dict[str, Any] = field(default_factory=dict)


class WorkflowEngine:
    """Executes workflows"""
    
    def __init__(self, data_dir: str = "data/workflows"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.workflows: Dict[str, Workflow] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self._load_workflows()
    
    def _load_workflows(self):
        """Load workflows from disk"""
        workflows_file = os.path.join(self.data_dir, "workflows.json")
        if os.path.exists(workflows_file):
            with open(workflows_file, "r") as f:
                data = json.load(f)
                for wid, wdata in data.items():
                    wdata["steps"] = {
                        sid: WorkflowStep(**sdata)
                        for sid, sdata in wdata["steps"].items()
                    }
                    self.workflows[wid] = Workflow(**wdata)
    
    def _save_workflows(self):
        """Save workflows to disk"""
        workflows_file = os.path.join(self.data_dir, "workflows.json")
        data = {}
        for wid, workflow in self.workflows.items():
            wdata = {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "steps": {
                    sid: {
                        "id": step.id,
                        "name": step.name,
                        "step_type": step.step_type.value,
                        "config": step.config,
                        "next_step": step.next_step,
                        "on_true": step.on_true,
                        "on_false": step.on_false,
                        "error_handler": step.error_handler
                    }
                    for sid, step in workflow.steps.items()
                },
                "start_step": workflow.start_step,
                "created_at": workflow.created_at,
                "version": workflow.version,
                "enabled": workflow.enabled
            }
            data[wid] = wdata
        
        with open(workflows_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def create_workflow(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        start_step: str = None
    ) -> Workflow:
        """Create a new workflow"""
        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        
        workflow_steps = {}
        for step_data in steps:
            step = WorkflowStep(
                id=step_data["id"],
                name=step_data.get("name", step_data["id"]),
                step_type=StepType(step_data.get("step_type", "ai_call")),
                config=step_data.get("config", {}),
                next_step=step_data.get("next_step"),
                on_true=step_data.get("on_true"),
                on_false=step_data.get("on_false"),
                error_handler=step_data.get("error_handler")
            )
            workflow_steps[step.id] = step
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            steps=workflow_steps,
            start_step=start_step or steps[0]["id"] if steps else None
        )
        
        self.workflows[workflow_id] = workflow
        self._save_workflows()
        return workflow
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by ID"""
        return self.workflows.get(workflow_id)
    
    def list_workflows(self) -> List[Dict]:
        """List all workflows"""
        return [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "steps_count": len(w.steps),
                "enabled": w.enabled,
                "version": w.version
            }
            for w in self.workflows.values()
        ]
    
    def execute_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any]
    ) -> WorkflowExecution:
        """Execute a workflow"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        execution = WorkflowExecution(
            id=f"exec_{uuid.uuid4().hex[:8]}",
            workflow_id=workflow_id,
            input_data=input_data,
            status="running",
            current_step=workflow.start_step,
            started_at=datetime.now().isoformat()
        )
        
        self.executions[execution.id] = execution
        
        # Execute steps
        try:
            current_step_id = workflow.start_step
            while current_step_id:
                step = workflow.steps.get(current_step_id)
                if not step:
                    break
                
                execution.current_step = current_step_id
                
                # Execute step
                result = self._execute_step(step, execution, workflow)
                execution.step_results[current_step_id] = result
                
                # Determine next step
                if step.step_type == StepType.CONDITION:
                    next_step_id = result.get("condition_result", False)
                    current_step_id = step.on_true if next_step_id else step.on_false
                else:
                    current_step_id = step.next_step
            
            execution.status = "completed"
            execution.completed_at = datetime.now().isoformat()
        
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            execution.completed_at = datetime.now().isoformat()
        
        return execution
    
    def _execute_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Execute a single workflow step"""
        if step.step_type == StepType.AI_CALL:
            return self._execute_ai_call(step, execution)
        elif step.step_type == StepType.TRANSFORM:
            return self._execute_transform(step, execution)
        elif step.step_type == StepType.CONDITION:
            return self._execute_condition(step, execution)
        elif step.step_type == StepType.OUTPUT:
            return self._execute_output(step, execution)
        else:
            return {"status": "skipped", "reason": "unsupported_step_type"}
    
    def _execute_ai_call(self, step: WorkflowStep, execution: WorkflowExecution) -> Dict:
        """Execute AI call step"""
        # This would integrate with the AI engine
        config = step.config
        return {
            "status": "completed",
            "model": config.get("model", "auto"),
            "prompt": config.get("prompt", ""),
            "response": "AI response placeholder"
        }
    
    def _execute_transform(self, step: WorkflowStep, execution: WorkflowExecution) -> Dict:
        """Execute transform step"""
        config = step.config
        transform_type = config.get("type", "extract")
        
        # Get input from previous step
        input_data = execution.input_data
        if execution.step_results:
            last_step = list(execution.step_results.keys())[-1]
            input_data = execution.step_results[last_step]
        
        # Apply transformation
        if transform_type == "extract":
            field = config.get("field", "")
            result = input_data.get(field, "")
        elif transform_type == "format":
            template = config.get("template", "")
            result = template.format(**input_data)
        else:
            result = input_data
        
        return {"status": "completed", "result": result}
    
    def _execute_condition(self, step: WorkflowStep, execution: WorkflowExecution) -> Dict:
        """Execute condition step"""
        config = step.config
        condition_type = config.get("type", "equals")
        
        # Get value to check
        value = config.get("value")
        compare_to = config.get("compare_to")
        
        if condition_type == "equals":
            result = value == compare_to
        elif condition_type == "not_equals":
            result = value != compare_to
        elif condition_type == "contains":
            result = compare_to in str(value) if value else False
        elif condition_type == "greater_than":
            result = float(value) > float(compare_to) if value and compare_to else False
        else:
            result = False
        
        return {"status": "completed", "condition_result": result}
    
    def _execute_output(self, step: WorkflowStep, execution: WorkflowExecution) -> Dict:
        """Execute output step"""
        config = step.config
        
        # Get input from previous step
        input_data = execution.input_data
        if execution.step_results:
            last_step = list(execution.step_results.keys())[-1]
            input_data = execution.step_results[last_step]
        
        # Set output
        output_field = config.get("field", "output")
        execution.output_data[output_field] = input_data.get("result", input_data)
        
        return {"status": "completed", "output": execution.output_data}
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution by ID"""
        return self.executions.get(execution_id)


# Global instance
workflow_engine = WorkflowEngine()
