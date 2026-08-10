"""Meeting notes generation (Sprint 16.4)."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.llm import StubChatModel
from api.app.agent.nodes.compose import make_compose_node
from api.app.agent.prompts import SYSTEM_MEETING_NOTES, build_compose_user_prompt
from api.app.agent.run import run_agent
from api.app.settings import Settings
from mcp_server.tools.notes import draft_meeting_notes

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _fake_search(**kwargs: Any) -> dict[str, Any]:
    return {
        "client_id": str(kwargs["client_id"]),
        "query": kwargs.get("query") or kwargs.get("topic") or "",
        "limit": int(kwargs.get("limit") or 8),
        "hit_count": 1,
        "hits": [
            {
                "point_id": "33333333-3333-3333-3333-333333333333",
                "score": 0.94,
                "text": "Alice: we decided to ship the beta Friday; Bob owns QA.",
                "kind": "slack_message",
                "client_id": str(kwargs["client_id"]),
                "channel": "C3",
                "ts": "300.0",
                "user": "U_ALICE",
                "thread_ts": None,
                "filename": None,
                "locator": None,
                "title": None,
                "source_format": None,
                "chunk_index": None,
            }
        ],
    }


def test_notes_prompt_includes_draft():
    text = build_compose_user_prompt(
        workflow="meeting_notes",
        question="Meeting notes from the beta call",
        evidence="[1] Alice: ship Friday",
        meeting_draft="# Meeting notes: beta\n\n## Decisions\n",
    )
    assert "Workflow: meeting_notes" in text
    assert "Draft outline:" in text
    assert "Meeting notes: beta" in text


def test_compose_uses_notes_prompt():
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
                    "point_id": "3",
                    "score": 0.94,
                    "text": "Alice: ship beta Friday.",
                    "kind": "slack_message",
                    "client_id": TENANT,
                    "user": "U_ALICE",
                    "label": "slack C3 ts=3",
                }
            ],
            "workflow": "meeting_notes",
            "model_tier": "sonnet",
            "question": "Meeting notes from the beta call",
            "meeting_draft": "# Meeting notes: beta\n\n## Action items\n",
        }
    )
    assert out["hedge"] is False
    assert seen["system"] == SYSTEM_MEETING_NOTES
    assert seen["tier"] == "sonnet"
    assert "Draft outline:" in seen["user"]


def test_run_agent_meeting_notes_via_mcp():
    calls: list[str] = []

    async def call_tool(name: str, arguments: dict[str, Any]):
        calls.append(name)
        if name == "draft_meeting_notes":
            return draft_meeting_notes(
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
        question="Meeting notes from yesterday's beta call",
        conversation_id="notes-1",
        settings=settings,
        checkpointer=MemorySaver(),
        mcp_call_tool=call_tool,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["workflow"] == "meeting_notes"
    assert out["model_tier"] == "sonnet"
    assert calls == ["draft_meeting_notes"]
    assert out["hedge"] is False
    assert out["meeting_draft"]
    assert "Meeting notes" in out["meeting_draft"]
    assert "stub:sonnet" in out["answer"]


def test_notes_helper_prefers_slack_then_widens():
    calls: list[str | None] = []

    def search(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs.get("kind"))
        if kwargs.get("kind") == "slack_message":
            return {
                "client_id": kwargs["client_id"],
                "query": kwargs["query"],
                "limit": kwargs.get("limit") or 8,
                "hit_count": 0,
                "hits": [],
            }
        return _fake_search(**kwargs)

    out = draft_meeting_notes(
        client_id=TENANT,
        topic="beta launch",
        search_tool_fn=search,
    )
    assert calls == ["slack_message", None]
    assert out["hedged"] is False
    assert "Action items" in out["markdown"]
