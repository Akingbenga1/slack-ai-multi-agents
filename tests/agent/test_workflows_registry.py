"""Workflow registry + classifier + tool Strategy (Sprint 25.2–25.4)."""

from __future__ import annotations

import pytest

from api.app.agent.state import WorkflowName
from api.app.agent.workflows import (
    TOOL_STRATEGIES,
    WORKFLOW_REGISTRY,
    classify_workflow,
    get_tool_strategy,
    get_workflow_meta,
    list_workflow_names,
)
from api.app.agent.workflows.rules import CLASSIFIER_RULES
from api.app.agent.workflows.tool_strategies import (
    MeetingDraftToolStrategy,
    OnboardingToolStrategy,
    RagToolStrategy,
    ReportToolStrategy,
)


def test_registry_covers_all_workflow_names():
    from typing import get_args

    names = set(get_args(WorkflowName))
    assert set(WORKFLOW_REGISTRY.keys()) == names
    assert set(list_workflow_names()) == names


def test_tool_strategies_cover_all_workflow_names():
    from typing import get_args

    names = set(get_args(WorkflowName))
    assert set(TOOL_STRATEGIES.keys()) == names
    for name in names:
        assert get_tool_strategy(name) is TOOL_STRATEGIES[name]


def test_tool_strategy_kinds():
    assert isinstance(get_tool_strategy("onboarding"), OnboardingToolStrategy)
    assert isinstance(get_tool_strategy("report"), ReportToolStrategy)
    assert isinstance(get_tool_strategy("meeting_brief"), MeetingDraftToolStrategy)
    assert isinstance(get_tool_strategy("qa"), RagToolStrategy)
    assert isinstance(get_tool_strategy("file_analyse"), RagToolStrategy)
    assert get_tool_strategy("not_a_real_workflow") is get_tool_strategy("qa")  # type: ignore[arg-type]


def test_get_workflow_meta_falls_back_to_qa():
    assert get_workflow_meta("qa").name == "qa"
    assert get_workflow_meta("not_a_real_workflow").name == "qa"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What is the refund policy?", "qa"),
        ("Please summarize yesterday's channel", "summarize"),
        ("What's the status on shipping?", "status"),
        ("Brief me for the launch sync", "meeting_brief"),
        ("Draft an agenda for the kickoff", "meeting_agenda"),
        ("Meeting notes from yesterday's call", "meeting_notes"),
        ("Generate a weekly report for the team", "report"),
        ("Start the onboarding process", "onboarding"),
        ("Analyse this attached financial report", "file_analyse"),
        ("Produce a PDF of competitor analysis from this report", "file_pdf_export"),
        ("Please rename the file to Q3-final.pdf", "file_rename"),
        ("Store this workflow for colleagues", "workflow_store"),
        ("List shared workflows", "workflow_list"),
        ("Copy this workflow", "workflow_copy"),
        ("Edit my workflow draft title to Launch", "workflow_edit"),
        ("Advise on how to operationalise this workflow", "workflow_advise"),
        ("", "unknown"),
    ],
)
def test_classify_parametrized_over_examples(question: str, expected: WorkflowName):
    assert classify_workflow(question) == expected


def test_classifier_rules_are_ordered_strategies():
    assert len(CLASSIFIER_RULES) >= 10
    # First hit wins — library store before generic file analyse
    assert classify_workflow("Store this attached workflow description") == "workflow_store"
    # PDF beats rename+analyse combined phrasing
    assert (
        classify_workflow(
            "I have a financial report — produce a PDF of competitor analysis "
            "and rename the financial report file"
        )
        == "file_pdf_export"
    )


def test_attachment_heuristic_rule():
    assert classify_workflow("Look at this carefully", has_attachments=True) == "file_analyse"
    assert classify_workflow("Look at this carefully", has_attachments=False) == "qa"


def test_delivery_hints_for_file_and_library():
    assert get_workflow_meta("file_pdf_export").delivery_hint == "pdf_upload"
    assert get_workflow_meta("file_rename").delivery_hint == "rename"
    assert get_workflow_meta("workflow_store").delivery_hint == "library_confirm"
    assert get_workflow_meta("qa").delivery_hint == "default"
