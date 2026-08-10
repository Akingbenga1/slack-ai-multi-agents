"""Meeting agenda generation (Sprint 16.3)."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.llm import StubChatModel
from api.app.agent.nodes.compose import make_compose_node
from api.app.agent.prompts import SYSTEM_MEETING_AGENDA, build_compose_user_prompt
from api.app.agent.run import run_agent
from api.app.settings import Settings
from mcp_server.tools.agenda import draft_meeting_agenda

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _fake_search(**kwargs: Any) -> dict[str, Any]:
    return {
        "client_id": str(kwargs["client_id"]),
        "query": kwargs.get("query") or kwargs.get("topic") or "",
        "limit": int(kwargs.get("limit") or 8),
        "hit_count": 1,
        "hits": [
            {
                "point_id": "22222222-2222-2222-2222-222222222222",
                "score": 0.93,
                "text": "Bob: hiring sync needs scorecard review and slot offers.",
                "kind": "slack_message",
                "client_id": str(kwargs["client_id"]),
                "channel": "C2",
                "ts": "200.0",
                "user": "U_BOB",
                "thread_ts": None,
                "filename": None,
                "locator": None,
                "title": None,
                "source_format": None,
                "chunk_index": None,
            }
        ],
    }


def test_agenda_prompt_includes_draft():
    text = build_compose_user_prompt(
        workflow="meeting_agenda",
        question="Draft an agenda for hiring",
        evidence="[1] Bob: scorecard",
        meeting_draft="# Meeting agenda: hiring\n\n1. **Open**\n",
    )
    assert "Workflow: meeting_agenda" in text
    assert "Draft outline:" in text
    assert "Meeting agenda: hiring" in text


def test_compose_uses_agenda_prompt():
    seen: dict[str, str] = {}

    class CaptureModel(StubChatModel):
        def complete(self, *, system, messages, model_tier):
            seen["system"] = system
            seen["user"] = messages[-1]["content"]
            seen["tier"] = model_tier
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
                    "point_id": "2",
                    "score": 0.93,
                    "text": "Bob: scorecard review.",
                    "kind": "slack_message",
                    "client_id": TENANT,
                    "user": "U_BOB",
                    "label": "slack C2 ts=2",
                }
            ],
            "workflow": "meeting_agenda",
            "model_tier": "sonnet",
            "question": "Draft an agenda for hiring",
            "meeting_draft": "# Meeting agenda: hiring\n\n1. **Open / goals**\n",
        }
    )
    assert out["hedge"] is False
    assert seen["system"] == SYSTEM_MEETING_AGENDA
    assert seen["tier"] == "sonnet"
    assert "Draft outline:" in seen["user"]


def test_run_agent_meeting_agenda_via_mcp():
    calls: list[str] = []

    async def call_tool(name: str, arguments: dict[str, Any]):
        calls.append(name)
        if name == "draft_meeting_agenda":
            return draft_meeting_agenda(
                search_tool_fn=_fake_search,
                **arguments,
            )
        raise AssertionError(f"unexpected tool {name}")

    settings = Settings(
        agent_checkpointer="memory",
        anthropic_api_key="",
        agent_retrieve_backend="mcp",
    )
    out = run_agent(
        client_id=TENANT,
        question="Draft an agenda for the hiring sync",
        conversation_id="agenda-1",
        settings=settings,
        checkpointer=MemorySaver(),
        mcp_call_tool=call_tool,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["workflow"] == "meeting_agenda"
    assert out["model_tier"] == "sonnet"
    assert calls == ["draft_meeting_agenda"]
    assert out["hedge"] is False
    assert out["meeting_draft"]
    assert "Meeting agenda" in out["meeting_draft"]
    assert "stub:sonnet" in out["answer"]
