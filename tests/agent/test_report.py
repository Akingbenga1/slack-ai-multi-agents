"""Recurring report workflow (Sprint 17.1)."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.llm import StubChatModel
from api.app.agent.nodes.compose import make_compose_node
from api.app.agent.nodes.route import classify_workflow
from api.app.agent.prompts import SYSTEM_REPORT, build_compose_user_prompt
from api.app.agent.run import run_agent, run_report
from api.app.settings import Settings
from mcp_server.tools.report import draft_report

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _fake_search(**kwargs: Any) -> dict[str, Any]:
    return {
        "client_id": str(kwargs["client_id"]),
        "query": kwargs.get("query") or kwargs.get("topic") or "",
        "limit": int(kwargs.get("limit") or 8),
        "hit_count": 1,
        "hits": [
            {
                "point_id": "44444444-4444-4444-4444-444444444444",
                "score": 0.93,
                "text": "Alice: we decided to freeze scope; open Q on launch date.",
                "kind": "slack_message",
                "client_id": str(kwargs["client_id"]),
                "channel": "C_REPORT",
                "ts": "400.0",
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


def test_classify_report_intents():
    assert classify_workflow("Generate a weekly report") == "report"
    assert classify_workflow("Post the team digest for the week") == "report"
    assert classify_workflow("Draft a recurring report") == "report"
    assert classify_workflow("weekly digest please") == "report"
    # Bare digest still summarize (unchanged)
    assert classify_workflow("Give me a digest of this thread") == "summarize"
    assert classify_workflow("What is the refund policy?") == "qa"


def test_report_prompt_includes_window_and_draft():
    text = build_compose_user_prompt(
        workflow="report",
        question="Recurring report for last 7 days",
        evidence="[1] Alice: freeze scope",
        meeting_draft="# Recurring report: last 7 days\n\n## Themes\n",
        report_window="last 7 days",
    )
    assert "Workflow: report" in text
    assert "Report window: last 7 days" in text
    assert "Draft outline:" in text
    assert "Themes" in text


def test_compose_uses_report_prompt():
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
                    "point_id": "4",
                    "score": 0.93,
                    "text": "Alice: freeze scope.",
                    "kind": "slack_message",
                    "client_id": TENANT,
                    "user": "U_ALICE",
                    "label": "slack C_REPORT ts=4",
                }
            ],
            "workflow": "report",
            "model_tier": "capable",
            "question": "Recurring report for last 7 days",
            "report_window": "last 7 days",
            "meeting_draft": "# Recurring report\n\n## Themes\n",
        }
    )
    assert out["hedge"] is False
    assert seen["system"] == SYSTEM_REPORT
    assert seen["tier"] == "capable"
    assert "Report window: last 7 days" in seen["user"]
    assert "Draft outline:" in seen["user"]


def test_draft_report_helper_sections():
    out = draft_report(
        client_id=TENANT,
        window_label="last 7 days",
        channel="C_REPORT",
        search_tool_fn=_fake_search,
    )
    assert out["hedged"] is False
    assert out["window_label"] == "last 7 days"
    headings = [s["heading"] for s in out["sections"]]
    assert headings == ["Themes", "Decisions", "Open questions"]
    assert "Recurring report" in out["markdown"]


def test_draft_report_hedge_when_empty():
    def empty_search(**kwargs: Any) -> dict[str, Any]:
        return {
            "client_id": kwargs["client_id"],
            "query": kwargs.get("query") or "",
            "limit": 8,
            "hit_count": 0,
            "hits": [],
        }

    out = draft_report(
        client_id=TENANT,
        window_label="last 7 days",
        kind="slack_message",
        search_tool_fn=empty_search,
    )
    assert out["hedged"] is True


def test_run_report_via_mcp():
    calls: list[str] = []

    async def fake_mcp(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append(name)
        assert arguments["client_id"] == TENANT
        assert arguments["window_label"] == "last 7 days"
        return draft_report(
            client_id=arguments["client_id"],
            window_label=arguments["window_label"],
            topic=arguments.get("topic"),
            channel=arguments.get("channel"),
            limit=int(arguments.get("limit") or 8),
            search_tool_fn=_fake_search,
        )

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_report(
        client_id=TENANT,
        window_label="last 7 days",
        channel="C_REPORT",
        settings=settings,
        checkpointer=MemorySaver(),
        mcp_call_tool=fake_mcp,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["workflow"] == "report"
    assert out["model_tier"] == "capable"
    assert out["report_window"] == "last 7 days"
    assert out["report_channel"] == "C_REPORT"
    assert out["hedge"] is False
    assert "draft_report" in calls
    assert out["answer"]


def test_run_agent_classifies_weekly_report():
    async def fake_mcp(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "draft_report":
            return draft_report(
                client_id=arguments["client_id"],
                window_label=arguments.get("window_label") or "last 7 days",
                topic=arguments.get("topic"),
                search_tool_fn=_fake_search,
            )
        raise AssertionError(f"unexpected tool {name}")

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="Generate a weekly report for the team",
        conversation_id="report-ask-1",
        settings=settings,
        checkpointer=MemorySaver(),
        mcp_call_tool=fake_mcp,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["workflow"] == "report"
    assert out["model_tier"] == "capable"
    assert out["hedge"] is False
