"""Task 15.4 / 27.4 — LangGraph tools node → MCP client (+ draft regression)."""

from __future__ import annotations

from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from mcp.shared.memory import create_connected_server_and_client_session

from api.app.agent.llm import StubChatModel
from api.app.agent.mcp_client import (
    call_mcp_tool_async,
    knowledge_result_from_mcp,
    search_knowledge_via_mcp,
    tool_result_payload,
)
from api.app.agent.run import run_agent
from api.app.qdrant.tenant import TenantFilterRequired
from api.app.settings import Settings
from mcp_server.server import create_mcp
from mcp_server.tools.agenda import draft_meeting_agenda
from mcp_server.tools.draft import draft_meeting_brief
from mcp_server.tools.notes import draft_meeting_notes
from mcp_server.tools.report import draft_report

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

# Tools-node → MCP draft path (Template Method tools + Adapter invoke).
_AGENT_DRAFT_CASES = [
    pytest.param(
        "Brief me for the launch sync",
        "meeting_brief",
        "draft_meeting_brief",
        draft_meeting_brief,
        "Meeting brief",
        id="brief",
    ),
    pytest.param(
        "Draft an agenda for the hiring sync",
        "meeting_agenda",
        "draft_meeting_agenda",
        draft_meeting_agenda,
        "Meeting agenda",
        id="agenda",
    ),
    pytest.param(
        "Meeting notes from yesterday's beta call",
        "meeting_notes",
        "draft_meeting_notes",
        draft_meeting_notes,
        "Meeting notes",
        id="notes",
    ),
    pytest.param(
        "Generate a weekly report for the team",
        "report",
        "draft_report",
        draft_report,
        "Recurring report",
        id="report",
    ),
]


def _fake_mcp_search(**kwargs: Any) -> dict[str, Any]:
    cid = kwargs.get("client_id")
    if not cid or not str(cid).strip():
        raise TenantFilterRequired("client_id is required")
    query = (kwargs.get("query") or "").strip()
    if not query:
        raise ValueError("query must be non-empty")
    return {
        "client_id": str(cid),
        "query": query,
        "limit": int(kwargs.get("limit") or 8),
        "hit_count": 1,
        "hits": [
            {
                "point_id": "11111111-1111-1111-1111-111111111111",
                "score": 0.92,
                "text": "Refunds are available within 30 days of purchase.",
                "kind": "document",
                "client_id": str(cid),
                "label": "document policy.csv",
                "channel": None,
                "ts": None,
                "user": None,
                "thread_ts": None,
                "filename": "policy.csv",
                "locator": "row:1",
                "title": None,
                "source_format": None,
                "chunk_index": None,
            }
        ],
    }


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_client_session_search_knowledge():
    """Real MCP ClientSession (in-memory server) — client path, not import-only."""
    app = create_mcp(search_fn=_fake_mcp_search, draft_fn=lambda **_: {})

    async def call_tool(name: str, arguments: dict[str, Any]):
        async with create_connected_server_and_client_session(
            app, raise_exceptions=True
        ) as session:
            return await session.call_tool(name, arguments)

    raw = await call_mcp_tool_async(
        "search_knowledge",
        {"client_id": TENANT, "query": "refund policy", "limit": 8},
        call_tool=call_tool,
    )
    payload = tool_result_payload(raw)
    kr = knowledge_result_from_mcp(payload)
    assert kr.client_id == TENANT
    assert len(kr.hits) == 1
    assert "30 days" in kr.hits[0].text


def test_run_agent_tools_node_via_mcp_inject():
    """Graph tools node → MCP client wrapper (injected transport)."""

    async def call_tool(name: str, arguments: dict[str, Any]):
        assert name == "search_knowledge"
        assert arguments["client_id"] == TENANT
        return _fake_mcp_search(**arguments)

    settings = Settings(
        agent_checkpointer="memory",
        anthropic_api_key="",
        agent_retrieve_backend="mcp",
    )
    out = run_agent(
        client_id=TENANT,
        question="What is the refund policy?",
        conversation_id="mcp-1",
        settings=settings,
        checkpointer=MemorySaver(),
        mcp_call_tool=call_tool,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["hedge"] is False
    assert len(out["retrieved_chunks"]) == 1
    assert out["retrieved_chunks"][0]["client_id"] == TENANT
    assert "stub:fast" in out["answer"]


def test_search_knowledge_via_mcp_sync_inject():
    async def call_tool(name: str, arguments: dict[str, Any]):
        return _fake_mcp_search(**arguments)

    result = search_knowledge_via_mcp(
        client_id=TENANT,
        query="refunds",
        call_tool=call_tool,
    )
    assert len(result.hits) == 1
    assert result.hits[0].filename == "policy.csv"


def test_invoke_mcp_adapter_inject():
    from api.app.agent.mcp_client import invoke_mcp

    async def call_tool(name: str, arguments: dict[str, Any]):
        assert name == "search_knowledge"
        return _fake_mcp_search(**arguments)

    payload = invoke_mcp(
        "search_knowledge",
        {"client_id": TENANT, "query": "refunds", "limit": 4},
        call_tool=call_tool,
    )
    assert payload["hit_count"] == 1
    assert payload["client_id"] == TENANT


@pytest.mark.parametrize(
    ("question", "workflow", "tool_name", "helper", "markdown_needle"),
    _AGENT_DRAFT_CASES,
)
def test_run_agent_grounded_draft_via_mcp(
    question: str,
    workflow: str,
    tool_name: str,
    helper: Any,
    markdown_needle: str,
):
    """Parametrized tools-node → MCP draft Adapter (Sprint 27.4 regression)."""
    calls: list[str] = []

    async def call_tool(name: str, arguments: dict[str, Any]):
        calls.append(name)
        if name == tool_name:
            return helper(search_tool_fn=_fake_mcp_search, **arguments)
        if name == "search_knowledge":
            return _fake_mcp_search(**arguments)
        raise AssertionError(f"unexpected tool {name}")

    settings = Settings(
        agent_checkpointer="memory",
        anthropic_api_key="",
        agent_retrieve_backend="mcp",
    )
    out = run_agent(
        client_id=TENANT,
        question=question,
        conversation_id=f"draft-{workflow}",
        settings=settings,
        checkpointer=MemorySaver(),
        mcp_call_tool=call_tool,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["workflow"] == workflow
    assert tool_name in calls
    assert out["hedge"] is False
    assert out.get("meeting_draft")
    assert markdown_needle in out["meeting_draft"]
    assert "stub:" in out["answer"]
