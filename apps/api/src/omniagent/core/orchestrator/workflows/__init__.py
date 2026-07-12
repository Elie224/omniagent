"""Module workflows declaratifs.

Expose :
- WorkflowRegistry, WorkflowDefinition, WorkflowStep
- workflow_registry (instance globale)
- register_default_workflows()
"""
from .registry import (
    WorkflowDefinition,
    WorkflowRegistry,
    WorkflowStep,
    workflow_registry,
)
from .defaults import register_default_workflows

__all__ = [
    "WorkflowDefinition",
    "WorkflowRegistry",
    "WorkflowStep",
    "workflow_registry",
    "register_default_workflows",
]