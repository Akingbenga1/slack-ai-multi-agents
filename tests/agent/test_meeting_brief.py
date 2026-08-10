"""Meeting brief generation (Sprint 16.2)."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.llm import StubChatModel
from api.app.agent.nodes.compose import make_compose_node
from api.app.agent.prompts import SYSTEM_MEETING_BRIEF, build_compose_user_prompt
from api.app.agent.run import run_agent
from api.app.settings import Settings
from mcp_server.tools.draft import draft_meeting_brief

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _fake_search(**kwargs: Any) -> dict[str, Any]:
    return {
        "client_id": str(kwargs["client_id"]),
        "query": kwargs.get("query") or kwargs.get("topic") or "",
        "limit": int(kwargs.get("limit") or 8),
        "hit_count": 1,
        "hits": [
            {
                "point_id": "11111111-1111-1111-1111-111111111111",
                "score": 0.91,
                "text": "Alice: launch is Friday; blockers cleared.",
                "kind": "slack_message",
                "client_id": str(kwargs["client_id"]),
                "channel": "C1",
                "ts": "100.0",
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


def test_build_prompt_includes_meeting_draft():
    text = build_compose_user_prompt(
        workflow="meeting_brief",
        question="Brief me for launch",
        evidence="[1] Alice: Friday",
        meeting_draft="# Meeting brief: launch\n\n## Purpose\n- Align\n",
    )
    assert "Workflow: meeting_brief" in text
    assert "Draft outline:" in text
    assert "Meeting brief: launch" in text
    assert "Polish" in text or "brief" in text.lower()


def test_compose_uses_brief_prompt_and_draft():
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
                    "point_id": "1",
                    "score": 0.91,
                    "text": "Alice: launch is Friday.",
                    "kind": "slack_message",
                    "client_id": TENANT,
                    "user": "U_ALICE",
                    "label": "slack C1 ts=1",
                }
            ],
            "workflow": "meeting_brief",
            "model_tier": "sonnet",
            "question": "Brief me for the launch sync",
            "meeting_draft": "# Meeting brief: launch\n\n## Purpose\n- Align on launch\n",
        }
    )
    assert out["hedge"] is False
    assert seen["system"] == SYSTEM_MEETING_BRIEF
    assert seen["tier"] == "sonnet"
    assert "Draft outline:" in seen["user"]
    assert "Workflow: meeting_brief" in seen["user"]


def test_run_agent_meeting_brief_via_mcp_draft():
    """tools node calls draft_meeting_brief for meeting_brief workflow."""
    calls: list[str] = []

    async def call_tool(name: str, arguments: dict[str, Any]):
        calls.append(name)
        if name == "draft_meeting_brief":
            return draft_meeting_brief(
                search_tool_fn=_fake_search,
                **arguments,
            )
        if name == "search_knowledge":
            return _fake_search(**arguments)
        raise AssertionError(f"unexpected tool {name}")

    settings = Settings(
        agent_checkpointer="memory",
        anthropic_api_key="",
        agent_retrieve_backend="mcp",
    )
    out = run_agent(
        client_id=TENANT,
        question="Brief me for the launch sync",
        conversation_id="brief-1",
        settings=settings,
        checkpointer=MemorySaver(),
        mcp_call_tool=call_tool,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["workflow"] == "meeting_brief"
    assert out["model_tier"] == "sonnet"
    assert "draft_meeting_brief" in calls
    assert "search_knowledge" not in calls
    assert out["hedge"] is False
    assert len(out["retrieved_chunks"]) >= 1
    assert out["meeting_draft"]
    assert "Meeting brief" in out["meeting_draft"]
    assert "stub:sonnet" in out["answer"]
