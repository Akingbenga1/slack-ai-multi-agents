"""Coordination-style prompts (Sprint 14.4)."""

from __future__ import annotations

from api.app.agent.chunks import format_evidence
from api.app.agent.llm import StubChatModel
from api.app.agent.nodes.compose import make_compose_node
from api.app.agent.nodes.route import classify_workflow
from api.app.agent.prompts import (
    SYSTEM_STATUS,
    SYSTEM_SUMMARIZE,
    build_compose_user_prompt,
    system_prompt_for,
)
from api.app.agent.run import run_agent
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from api.app.settings import Settings
from langgraph.checkpoint.memory import MemorySaver

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_classify_coordination_intents():
    assert classify_workflow("What's the status on the launch?") == "status"
    assert classify_workflow("Who said we should delay the release?") == "status"
    assert classify_workflow("Who mentioned the budget cap?") == "status"
    assert classify_workflow("Any update on onboarding?") == "status"
    assert classify_workflow("Please summarize yesterday's channel discussion") == "summarize"
    assert classify_workflow("Catch me up on this thread") == "summarize"
    assert classify_workflow("What is the refund policy?") == "qa"


def test_system_prompts_differ_by_workflow():
    qa = system_prompt_for("qa")
    status = system_prompt_for("status")
    summarize = system_prompt_for("summarize")
    assert status == SYSTEM_STATUS
    assert summarize == SYSTEM_SUMMARIZE
    assert "who said" in status.lower() or "attribution" in status.lower()
    assert "summar" in summarize.lower()
    assert status != qa
    assert summarize != qa
    assert summarize != status


def test_format_evidence_includes_speaker():
    block = format_evidence(
        [
            {
                "label": "slack C1 ts=1.0",
                "kind": "slack_message",
                "user": "U_ALICE",
                "channel": "C1",
                "ts": "1.0",
                "text": "Ship Friday.",
            }
        ]
    )
    assert "user=U_ALICE" in block
    assert "Ship Friday." in block


def test_compose_uses_status_system_prompt():
    """Compose selects coordination system prompt from workflow."""
    seen: dict[str, str] = {}

    class CaptureModel(StubChatModel):
        def complete(self, *, system, messages, model_tier):
            seen["system"] = system
            seen["user"] = messages[-1]["content"]
            return super().complete(
                system=system, messages=messages, model_tier=model_tier
            )

    node = make_compose_node(chat_model=CaptureModel())
    out = node(
        {
            "client_id": TENANT,
            "messages": [],
            "retrieved_chunks": [
                {
                    "point_id": "1",
                    "score": 0.95,
                    "text": "Alice said launch is Friday.",
                    "kind": "slack_message",
                    "client_id": TENANT,
                    "user": "U_ALICE",
                    "label": "slack C1 ts=1",
                }
            ],
            "workflow": "status",
            "model_tier": "sonnet",
            "question": "Who said launch is Friday?",
        }
    )
    assert out["hedge"] is False
    assert seen["system"] == SYSTEM_STATUS
    assert "Workflow: status" in seen["user"]
    assert "who-said-what" in seen["user"].lower() or "status" in seen["user"].lower()
    assert "user=U_ALICE" in seen["user"]


def test_run_agent_status_workflow_escalates():
    def search(*, client_id, query, limit=8, settings=None, **_kw):
        hit = KnowledgeCitation(
            point_id="11111111-1111-1111-1111-111111111111",
            score=0.92,
            text="Bob: blockers cleared; shipping Monday.",
            kind="slack_message",
            client_id=TENANT,
            channel="C9",
            ts="100.1",
            user="U_BOB",
        )
        return KnowledgeSearchResult(
            client_id=str(client_id),
            query=query,
            hits=[hit],
            limit=limit,
        )

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="What's the status on shipping?",
        conversation_id="coord-1",
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=search,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["workflow"] == "status"
    assert out["model_tier"] == "sonnet"
    assert any(f.startswith("workflow:status") for f in out["complexity_flags"])
    assert out["hedge"] is False


def test_build_user_prompt_instruction():
    text = build_compose_user_prompt(
        workflow="summarize",
        question="Summarize this thread",
        evidence="[1] hello",
    )
    assert "Workflow: summarize" in text
    assert "Instruction:" in text
    assert "Summarize" in text or "summar" in text.lower()
