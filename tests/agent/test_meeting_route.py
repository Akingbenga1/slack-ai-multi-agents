"""Meeting intent routing (Sprint 16.1) — classification removed."""

from __future__ import annotations

from api.app.agent.policy import choose_model_tier, detect_complexity_flags
from api.app.agent.prompts import (
    SYSTEM_MEETING_AGENDA,
    SYSTEM_MEETING_BRIEF,
    SYSTEM_MEETING_NOTES,
    system_prompt_for,
)


def test_meeting_workflows_escalate_capable():
    for wf in ("meeting_brief", "meeting_agenda", "meeting_notes"):
        flags = detect_complexity_flags("some question", workflow=wf)
        assert f"workflow:{wf}" in flags
        assert choose_model_tier(flags=flags) == "capable"


def test_meeting_system_prompts():
    assert system_prompt_for("meeting_brief") == SYSTEM_MEETING_BRIEF
    assert system_prompt_for("meeting_agenda") == SYSTEM_MEETING_AGENDA
    assert system_prompt_for("meeting_notes") == SYSTEM_MEETING_NOTES
    assert "brief" in SYSTEM_MEETING_BRIEF.lower()
    assert "agenda" in SYSTEM_MEETING_AGENDA.lower()
    assert "notes" in SYSTEM_MEETING_NOTES.lower()
