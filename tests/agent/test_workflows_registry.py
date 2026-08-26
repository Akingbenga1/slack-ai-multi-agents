"""Workflow registry + tool Strategy (Sprint 25.2–25.4).

Classification tests removed — the orchestrator LLM now decides workflow type.
"""

from __future__ import annotations

from api.app.agent.workflows import (
    TOOL_STRATEGIES,
    WORKFLOW_REGISTRY,
    get_tool_strategy,
    get_workflow_meta,
    list_workflow_names,
)
from api.app.agent.workflows.tool_strategies import (
    MeetingDraftToolStrategy,
    OnboardingToolStrategy,
    RagToolStrategy,
    ReportToolStrategy,
)


def test_registry_has_entries():
    assert len(WORKFLOW_REGISTRY) >= 1
    assert len(list_workflow_names()) >= 1


def test_tool_strategy_kinds():
    assert isinstance(get_tool_strategy("onboarding"), OnboardingToolStrategy)
    assert isinstance(get_tool_strategy("report"), ReportToolStrategy)
    assert isinstance(get_tool_strategy("meeting_brief"), MeetingDraftToolStrategy)
    assert isinstance(get_tool_strategy("qa"), RagToolStrategy)
    assert isinstance(get_tool_strategy("file_analyse"), RagToolStrategy)
    assert get_tool_strategy("not_a_real_workflow") is get_tool_strategy("qa")


def test_get_workflow_meta_falls_back_to_qa():
    assert get_workflow_meta("qa").name == "qa"
    assert get_workflow_meta("not_a_real_workflow").name == "qa"


def test_delivery_hints_for_file_and_library():
    assert get_workflow_meta("file_pdf_export").delivery_hint == "pdf_upload"
    assert get_workflow_meta("file_rename").delivery_hint == "rename"
    assert get_workflow_meta("workflow_store").delivery_hint == "library_confirm"
    assert get_workflow_meta("qa").delivery_hint == "default"
