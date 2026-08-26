"""MCP client transport tests (bundled tools removed — DB-only discovery)."""

from __future__ import annotations

from typing import Any

import pytest

from api.app.agent.mcp_client import (
    call_mcp_tool_async,
    invoke_mcp,
    knowledge_result_from_mcp,
    tool_result_payload,
)
from api.app.qdrant.tenant import TenantFilterRequired

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


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
async def test_call_mcp_tool_async_inject():
    """Injected call_tool transport works end-to-end."""

    async def call_tool(name: str, arguments: dict[str, Any]):
        assert name == "search_knowledge"
        return _fake_mcp_search(**arguments)

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


def test_invoke_mcp_adapter_inject():
    """invoke_mcp passes through injected call_tool correctly."""

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
