"""Meeting intent routing (Sprint 16.1)."""

from __future__ import annotations

from api.app.agent.nodes.route import classify_workflow
from api.app.agent.policy import choose_model_tier, detect_complexity_flags
from api.app.agent.prompts import (
    SYSTEM_MEETING_AGENDA,
    SYSTEM_MEETING_BRIEF,
    SYSTEM_MEETING_NOTES,
    system_prompt_for,
)


def test_classify_meeting_brief():
    assert classify_workflow("Brief me for the launch sync") == "meeting_brief"
    assert classify_workflow("Prepare a meeting brief on onboarding") == "meeting_brief"
    assert classify_workflow("Pre-meeting prep for the budget review") == "meeting_brief"
    assert classify_workflow("Draft a brief for the Q3 planning call") == "meeting_brief"
    assert classify_workflow("Prep me for tomorrow's standup") == "meeting_brief"


def test_classify_meeting_agenda():
    assert classify_workflow("Draft an agenda for the kickoff") == "meeting_agenda"
    assert classify_workflow("What's a good meeting agenda for hiring?") == "meeting_agenda"
    assert classify_workflow("Build an agenda for Friday's sync") == "meeting_agenda"


def test_classify_meeting_notes():
    assert classify_workflow("Meeting notes from yesterday's call") == "meeting_notes"
    assert classify_workflow("Take notes for the design discussion") == "meeting_notes"
    assert classify_workflow("Capture meeting notes from recent context") == "meeting_notes"
    assert classify_workflow("Notes from the meeting about pricing") == "meeting_notes"


def test_meeting_intents_beat_summarize_and_status():
    # Agenda / brief phrasing wins over generic summarize/status cues
    assert (
        classify_workflow("Summarize context into a meeting brief for launch")
        == "meeting_brief"
    )
    assert (
        classify_workflow("Draft an agenda and include latest status")
        == "meeting_agenda"
    )


def test_non_meeting_unchanged():
    assert classify_workflow("What is the refund policy?") == "qa"
    assert classify_workflow("Give me a brief overview of the refund policy") == "qa"
    assert classify_workflow("Please summarize yesterday's channel") == "summarize"
    assert classify_workflow("What's the status on shipping?") == "status"
    assert classify_workflow("Who said we should delay?") == "status"


def test_meeting_workflows_escalate_sonnet():
    for wf, q in (
        ("meeting_brief", "Brief me for the launch sync"),
        ("meeting_agenda", "Draft an agenda for kickoff"),
        ("meeting_notes", "Meeting notes from yesterday"),
    ):
        assert classify_workflow(q) == wf
        flags = detect_complexity_flags(q, workflow=wf)
        assert f"workflow:{wf}" in flags
        assert choose_model_tier(flags=flags) == "sonnet"


def test_meeting_system_prompts():
    assert system_prompt_for("meeting_brief") == SYSTEM_MEETING_BRIEF
    assert system_prompt_for("meeting_agenda") == SYSTEM_MEETING_AGENDA
    assert system_prompt_for("meeting_notes") == SYSTEM_MEETING_NOTES
    assert "brief" in SYSTEM_MEETING_BRIEF.lower()
    assert "agenda" in SYSTEM_MEETING_AGENDA.lower()
    assert "notes" in SYSTEM_MEETING_NOTES.lower()
