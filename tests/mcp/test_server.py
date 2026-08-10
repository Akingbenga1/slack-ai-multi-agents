"""MCP server tests — in-memory transport + stub search."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from api.app.qdrant.tenant import TenantFilterRequired
from mcp_server.server import create_mcp
from mcp_server.tools.agenda import draft_meeting_agenda
from mcp_server.tools.draft import draft_meeting_brief
from mcp_server.tools.notes import draft_meeting_notes
from mcp_server.tools.report import draft_report
from mcp_server.tools.search import search_knowledge_tool

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _stub_search_result(
    *,
    client_id: str,
    query: str,
    limit: int = 8,
    hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "client_id": client_id,
        "query": query,
        "limit": limit,
        "hit_count": len(hits or []),
        "hits": hits or [],
    }


def _sample_hit(client_id: str = TENANT) -> dict[str, Any]:
    return {
        "point_id": "p1",
        "score": 0.91,
        "text": "Onboarding checklist: laptop, Slack, and buddy assigned.",
        "kind": "slack_message",
        "client_id": client_id,
        "label": "slack C_KNOWLEDGE ts=1.0",
        "channel": "C_KNOWLEDGE",
        "ts": "1.0",
        "user": "U123",
        "thread_ts": None,
        "filename": None,
        "locator": None,
        "title": None,
        "source_format": None,
        "chunk_index": None,
    }


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def mcp_session() -> AsyncGenerator[ClientSession, None]:
    def fake_search(**kwargs: Any) -> dict[str, Any]:
        cid = kwargs.get("client_id")
        if not cid or not str(cid).strip():
            raise TenantFilterRequired("client_id is required")
        query = (kwargs.get("query") or "").strip()
        if not query:
            raise ValueError("query must be non-empty")
        return _stub_search_result(
            client_id=str(cid),
            query=query,
            limit=int(kwargs.get("limit") or 8),
            hits=[_sample_hit(str(cid))],
        )

    def fake_draft(**kwargs: Any) -> dict[str, Any]:
        return draft_meeting_brief(search_tool_fn=fake_search, **kwargs)

    def fake_agenda(**kwargs: Any) -> dict[str, Any]:
        return draft_meeting_agenda(search_tool_fn=fake_search, **kwargs)

    def fake_notes(**kwargs: Any) -> dict[str, Any]:
        return draft_meeting_notes(search_tool_fn=fake_search, **kwargs)

    def fake_report(**kwargs: Any) -> dict[str, Any]:
        return draft_report(search_tool_fn=fake_search, **kwargs)

    def fake_rename(**kwargs: Any) -> dict[str, Any]:
        cid = kwargs.get("client_id")
        if not cid or not str(cid).strip():
            raise TenantFilterRequired("client_id is required")
        new_name = (kwargs.get("new_filename") or "").strip()
        if not new_name:
            raise ValueError("new_filename must be non-empty")
        return {
            "ok": True,
            "mode": "org_copy",
            "client_id": str(cid),
            "new_filename": new_name,
            "stored_relative_path": kwargs.get("stored_relative_path"),
            "confirmation": f"Renamed → {new_name}",
        }

    def fake_get_workflow(**kwargs: Any) -> dict[str, Any]:
        cid = kwargs.get("client_id")
        if not cid or not str(cid).strip():
            raise TenantFilterRequired("client_id is required")
        tid = (kwargs.get("template_id") or "").strip()
        if not tid:
            raise ValueError("template_id must be non-empty")
        return {
            "ok": True,
            "client_id": str(cid),
            "template": {
                "id": tid,
                "client_id": str(cid),
                "title": "Stub Workflow",
                "body_text": "1. Intake\n2. Review\n3. Ship",
                "visibility": "shared",
            },
        }

    def fake_advise(**kwargs: Any) -> dict[str, Any]:
        from mcp_server.tools.workflow import advise_workflow as advise_fn

        return advise_fn(search_tool_fn=fake_search, **kwargs)

    app = create_mcp(
        search_fn=fake_search,
        draft_fn=fake_draft,
        agenda_fn=fake_agenda,
        notes_fn=fake_notes,
        report_fn=fake_report,
        rename_fn=fake_rename,
        get_workflow_fn=fake_get_workflow,
        advise_workflow_fn=fake_advise,
    )
    async with create_connected_server_and_client_session(
        app, raise_exceptions=True
    ) as session:
        yield session


@pytest.mark.anyio
async def test_list_tools(mcp_session: ClientSession):
    tools = await mcp_session.list_tools()
    names = sorted(t.name for t in tools.tools)
    assert names == [
        "advise_workflow",
        "draft_meeting_agenda",
        "draft_meeting_brief",
        "draft_meeting_notes",
        "draft_report",
        "get_workflow_template",
        "rename_slack_file",
        "search_knowledge",
        "start_onboarding",
    ]


@pytest.mark.anyio
async def test_search_knowledge_requires_tenant(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "search_knowledge",
        {"client_id": "", "query": "onboarding"},
    )
    assert result.isError


@pytest.mark.anyio
async def test_search_knowledge_ok(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "search_knowledge",
        {"client_id": TENANT, "query": "onboarding checklist"},
    )
    assert not result.isError
    assert result.structuredContent is not None
    sc = result.structuredContent
    assert sc["client_id"] == TENANT
    assert sc["hit_count"] == 1
    assert sc["hits"][0]["channel"] == "C_KNOWLEDGE"


# Grounded draft tools (Template Method + create_mcp registry row).
# Adding a tool = outline_fn + registry row + one row here.
_GROUNDED_DRAFT_OK = [
    pytest.param(
        "draft_meeting_brief",
        {"client_id": TENANT, "topic": "onboarding checklist"},
        "Meeting brief",
        "sections",
        ("Context from knowledge",),
        id="brief",
    ),
    pytest.param(
        "draft_meeting_agenda",
        {"client_id": TENANT, "topic": "onboarding checklist"},
        "Meeting agenda",
        "items",
        (),
        id="agenda",
    ),
    pytest.param(
        "draft_meeting_notes",
        {"client_id": TENANT, "topic": "onboarding checklist"},
        "Meeting notes",
        "sections",
        ("Action items", "Decisions"),
        id="notes",
    ),
    pytest.param(
        "draft_report",
        {"client_id": TENANT, "window_label": "last 7 days"},
        "Recurring report",
        "sections",
        ("Themes", "Decisions", "Open questions"),
        id="report",
    ),
]

_GROUNDED_DRAFT_HEDGE = [
    pytest.param(
        draft_meeting_brief,
        {"client_id": TENANT, "topic": "mystery topic"},
        id="brief",
    ),
    pytest.param(
        draft_meeting_agenda,
        {"client_id": TENANT, "topic": "mystery topic"},
        id="agenda",
    ),
    pytest.param(
        draft_meeting_notes,
        {"client_id": TENANT, "topic": "mystery topic", "kind": "slack_message"},
        id="notes",
    ),
    pytest.param(
        draft_report,
        {
            "client_id": TENANT,
            "window_label": "last 7 days",
            "kind": "slack_message",
        },
        id="report",
    ),
]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "markdown_needle", "shape_key", "headings"),
    _GROUNDED_DRAFT_OK,
)
async def test_grounded_draft_tool_ok(
    mcp_session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
    markdown_needle: str,
    shape_key: str,
    headings: tuple[str, ...],
):
    result = await mcp_session.call_tool(tool_name, arguments)
    assert not result.isError
    sc = result.structuredContent
    assert sc is not None
    assert sc["client_id"] == TENANT
    assert sc["hedged"] is False
    assert markdown_needle in sc["markdown"]
    if shape_key == "items":
        assert len(sc["items"]) >= 3
    else:
        found = {s["heading"] for s in sc["sections"]}
        for h in headings:
            assert h in found


def test_search_knowledge_tool_fail_closed():
    with pytest.raises(TenantFilterRequired):
        search_knowledge_tool(client_id=None, query="x")
    with pytest.raises(TenantFilterRequired):
        search_knowledge_tool(client_id="  ", query="x")


@pytest.mark.parametrize(("helper", "kwargs"), _GROUNDED_DRAFT_HEDGE)
def test_grounded_draft_helper_hedge_when_empty(helper: Any, kwargs: dict[str, Any]):
    def empty_search(**search_kwargs: Any) -> dict[str, Any]:
        return _stub_search_result(
            client_id=search_kwargs["client_id"],
            query=search_kwargs.get("query")
            or search_kwargs.get("topic")
            or "",
            hits=[],
        )

    out = helper(search_tool_fn=empty_search, **kwargs)
    assert out["hedged"] is True
    assert "Insufficient" in out["note"] or "placeholder" in out["note"].lower()


@pytest.mark.anyio
async def test_start_onboarding_ok(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "start_onboarding",
        {"client_id": TENANT},
    )
    assert not result.isError
    sc = result.structuredContent
    assert sc is not None
    assert sc["client_id"] == TENANT
    assert sc["configured"] is False
    assert sc["status"] == "not_configured"
    assert "not configured" in sc["message"].lower()


@pytest.mark.anyio
async def test_start_onboarding_requires_tenant(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "start_onboarding",
        {"client_id": ""},
    )
    assert result.isError


@pytest.mark.anyio
async def test_rename_slack_file_ok(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "rename_slack_file",
        {
            "client_id": TENANT,
            "new_filename": "Q3-final.csv",
            "stored_relative_path": f"{TENANT}/u1_report.csv",
        },
    )
    assert not result.isError
    sc = result.structuredContent
    assert sc is not None
    assert sc["ok"] is True
    assert sc["new_filename"] == "Q3-final.csv"


@pytest.mark.anyio
async def test_rename_slack_file_requires_tenant(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "rename_slack_file",
        {"client_id": "", "new_filename": "x.csv"},
    )
    assert result.isError


@pytest.mark.anyio
async def test_get_workflow_template_ok(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "get_workflow_template",
        {
            "client_id": TENANT,
            "template_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert not result.isError
    sc = result.structuredContent
    assert sc is not None
    assert sc["ok"] is True
    assert sc["template"]["title"] == "Stub Workflow"


@pytest.mark.anyio
async def test_get_workflow_template_requires_tenant(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "get_workflow_template",
        {"client_id": "", "template_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert result.isError


@pytest.mark.anyio
async def test_advise_workflow_ok(mcp_session: ClientSession):
    result = await mcp_session.call_tool(
        "advise_workflow",
        {
            "client_id": TENANT,
            "question": "How can we make this workflow work?",
            "body_text": "Step A: gather inputs\nStep B: review with lead\nStep C: publish",
            "title": "Channel publish flow",
        },
    )
    assert not result.isError
    sc = result.structuredContent
    assert sc is not None
    assert sc["hedged"] is False
    assert "Workflow advice" in sc["markdown"]
    assert sc["note"] == "grounded_in_workflow_file"


def test_advise_workflow_hedges_without_file():
    from mcp_server.tools.workflow import advise_workflow

    out = advise_workflow(
        client_id=TENANT,
        question="advise on workflow",
        body_text="",
        search_tool_fn=lambda **kwargs: _stub_search_result(
            client_id=kwargs["client_id"],
            query=kwargs.get("query") or "",
            hits=[],
        ),
    )
    assert out["hedged"] is True
    assert "Insufficient" in out["markdown"]


def test_start_onboarding_helper():
    from mcp_server.tools.onboarding import (
        ONBOARDING_NOT_CONFIGURED_MESSAGE,
        start_onboarding,
    )

    out = start_onboarding(client_id=TENANT)
    assert out["configured"] is False
    assert out["message"] == ONBOARDING_NOT_CONFIGURED_MESSAGE
    assert "not configured" in out["message"].lower()
    # Must not invent a multi-step process
    assert "step 1" not in out["message"].lower()
