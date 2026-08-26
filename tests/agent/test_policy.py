"""Model-tier policy (Task 13.3)."""

from api.app.agent.policy import choose_model_tier, detect_complexity_flags


def test_default_fast_simple_qa():
    flags = detect_complexity_flags("What is the refund policy?", workflow="qa")
    assert flags == []
    assert choose_model_tier(flags=flags) == "fast"


def test_escalate_on_compare():
    flags = detect_complexity_flags(
        "Compare the old and new onboarding checklists",
        workflow="qa",
    )
    assert "compare" in flags
    assert choose_model_tier(flags=flags) == "capable"


def test_escalate_on_summarize_workflow():
    flags = detect_complexity_flags(
        "Please summarize yesterday's channel discussion",
        workflow="summarize",
    )
    assert any(f.startswith("workflow:") for f in flags)
    assert choose_model_tier(flags=flags) == "capable"
