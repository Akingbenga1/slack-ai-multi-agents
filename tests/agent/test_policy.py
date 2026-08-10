"""Model-tier policy (Task 13.3)."""

from api.app.agent.policy import choose_model_tier, detect_complexity_flags
from api.app.agent.nodes.route import classify_workflow


def test_default_haiku_simple_qa():
    flags = detect_complexity_flags("What is the refund policy?", workflow="qa")
    assert flags == []
    assert choose_model_tier(flags=flags) == "haiku"


def test_escalate_on_compare():
    flags = detect_complexity_flags(
        "Compare the old and new onboarding checklists",
        workflow="qa",
    )
    assert "compare" in flags
    assert choose_model_tier(flags=flags) == "sonnet"


def test_escalate_on_summarize_workflow():
    q = "Please summarize yesterday's channel discussion"
    assert classify_workflow(q) == "summarize"
    flags = detect_complexity_flags(q, workflow="summarize")
    assert any(f.startswith("workflow:") for f in flags)
    assert choose_model_tier(flags=flags) == "sonnet"


def test_classify_status():
    assert classify_workflow("What's the status on the launch?") == "status"
    assert classify_workflow("Who said the deadline moved?") == "status"
