"""Onboarding stub workflow (Sprint 18.1)."""

from __future__ import annotations

from api.app.agent.policy import choose_model_tier, detect_complexity_flags
from api.app.agent.workflows.tool_strategies import ONBOARDING_NOT_CONFIGURED_MESSAGE


TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_onboarding_does_not_escalate_capable():
    flags = detect_complexity_flags("Start onboarding", workflow="onboarding")
    assert "workflow:onboarding" not in flags
    assert choose_model_tier(flags=flags) == "fast"
