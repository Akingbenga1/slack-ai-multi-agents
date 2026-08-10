"""File-transform workflow routing (Sprint 23.2)."""

from __future__ import annotations

from api.app.agent.nodes.route import classify_workflow
from api.app.agent.policy import detect_complexity_flags
from api.app.agent.prompts import system_prompt_for


def test_classify_file_analyse():
    assert (
        classify_workflow("Analyse this attached financial report")
        == "file_analyse"
    )
    assert classify_workflow("Review the attached document please") == "file_analyse"
    assert (
        classify_workflow("Based on this file, what are the risks?") == "file_analyse"
    )


def test_classify_file_pdf_export():
    assert (
        classify_workflow("Produce a PDF of competitor analysis from this report")
        == "file_pdf_export"
    )
    assert classify_workflow("Generate a PDF deliverable please") == "file_pdf_export"
    # J10 combined ask prefers PDF export over bare rename
    assert (
        classify_workflow(
            "I have a financial report — produce a PDF of competitor analysis "
            "and rename the financial report file"
        )
        == "file_pdf_export"
    )


def test_classify_file_rename():
    assert classify_workflow("Please rename the file to Q3-final.pdf") == "file_rename"
    assert classify_workflow("Rename this attachment") == "file_rename"


def test_has_attachments_heuristic():
    assert (
        classify_workflow("Look at this carefully", has_attachments=True)
        == "file_analyse"
    )
    assert classify_workflow("Look at this carefully", has_attachments=False) == "qa"


def test_file_workflows_escalate_and_have_prompts():
    for wf in ("file_analyse", "file_pdf_export"):
        flags = detect_complexity_flags("analyse competitors", workflow=wf)
        assert f"workflow:{wf}" in flags
        prompt = system_prompt_for(wf)
        assert "Evidence" in prompt or "evidence" in prompt.lower()


def test_non_file_asks_unchanged():
    assert classify_workflow("What is the refund policy?") == "qa"
    assert classify_workflow("Prepare a meeting brief on launch") == "meeting_brief"
