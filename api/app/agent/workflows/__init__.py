"""Workflow Strategy registry (Sprint 25).

Registration point for classifier rules, metadata, and tool strategies.
See ``registry.py`` module docstring for how to add a workflow.
"""

from __future__ import annotations

from api.app.agent.workflows.intents import (
    question_requests_pdf_export,
    question_requests_rename,
    question_requests_workflow_advice,
)
from api.app.agent.workflows.registry import (
    WORKFLOW_REGISTRY,
    WorkflowMeta,
    get_workflow_meta,
    iter_workflow_meta,
    list_workflow_names,
)
from api.app.agent.workflows.rules import (
    CLASSIFIER_RULES,
    ClassifierRule,
    classify_workflow,
)
from api.app.agent.workflows.tool_strategies import (
    TOOL_STRATEGIES,
    ToolStrategy,
    get_tool_strategy,
)

__all__ = [
    "CLASSIFIER_RULES",
    "TOOL_STRATEGIES",
    "WORKFLOW_REGISTRY",
    "ClassifierRule",
    "ToolStrategy",
    "WorkflowMeta",
    "classify_workflow",
    "get_tool_strategy",
    "get_workflow_meta",
    "iter_workflow_meta",
    "list_workflow_names",
    "question_requests_pdf_export",
    "question_requests_rename",
    "question_requests_workflow_advice",
]
