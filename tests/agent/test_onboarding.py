"""Onboarding stub workflow (Sprint 18.1)."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.llm import StubChatModel
from api.app.agent.nodes.route import classify_workflow
from api.app.agent.policy import choose_model_tier, detect_complexity_flags
from api.app.agent.run import run_agent
from api.app.settings import Settings
from mcp_server.tools.onboarding import (
    ONBOARDING_NOT_CONFIGURED_MESSAGE,
    start_onboarding,
)

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_classify_onboarding_start():
    assert classify_workflow("Start onboarding") == "onboarding"
    assert classify_workflow("Begin the client onboarding") == "onboarding"
    assert classify_workflow("Kick off onboarding for Acme") == "onboarding"
    assert classify_workflow("Run the onboarding process") == "onboarding"
    assert classify_workflow("What's our onboarding workflow?") == "onboarding"
    assert classify_workflow("start_onboarding") == "onboarding"


def test_onboarding_knowledge_qa_stays_qa():
    # Corpus-style asks must not hit the process stub
    assert classify_workflow("onboarding checklist for new hires") == "qa"
    assert classify_workflow("What is the refund policy?") == "qa"
    assert (
        classify_workflow("Prepare a meeting brief on onboarding") == "meeting_brief"
    )


def test_onboarding_does_not_escalate_capable():
    q = "Start onboarding"
    assert classify_workflow(q) == "onboarding"
    flags = detect_complexity_flags(q, workflow="onboarding")
    assert "workflow:onboarding" not in flags
    assert choose_model_tier(flags=flags) == "fast"


def test_run_agent_onboarding_stub():
    calls: list[str] = []

    async def fake_mcp(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append(name)
        assert arguments["client_id"] == TENANT
        if name == "start_onboarding":
            return start_onboarding(client_id=arguments["client_id"])
        raise AssertionError(f"unexpected tool {name}")

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="Start onboarding please",
        conversation_id="onboarding-1",
        settings=settings,
        checkpointer=MemorySaver(),
        mcp_call_tool=fake_mcp,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["workflow"] == "onboarding"
    assert out["hedge"] is False
    assert out["usage_tokens"] == 0
    assert out["answer"] == ONBOARDING_NOT_CONFIGURED_MESSAGE
    assert "start_onboarding" in calls
    assert "not configured" in out["answer"].lower()
