"""File-transform workflow routing (Sprint 23.2) — classification removed."""

from __future__ import annotations

from api.app.agent.policy import detect_complexity_flags
from api.app.agent.prompts import system_prompt_for


def test_file_workflows_escalate_and_have_prompts():
    for wf in ("file_analyse", "file_pdf_export"):
        flags = detect_complexity_flags("analyse competitors", workflow=wf)
        assert f"workflow:{wf}" in flags
        prompt = system_prompt_for(wf)
        assert "Evidence" in prompt or "evidence" in prompt.lower()
