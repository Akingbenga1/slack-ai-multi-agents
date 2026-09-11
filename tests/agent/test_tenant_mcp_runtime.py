"""Unit tests for MCP OAuth helpers and tenant MCP runtime wrappers."""

from __future__ import annotations

from api.app.agent.tenant_mcp import _normalize_arguments, _tool_id, usage_as_dicts, McpUsageEvent
from api.app.mcp_servers.oauth import _pkce_pair


def test_pkce_pair_shapes():
    verifier, challenge = _pkce_pair()
    assert len(verifier) >= 32
    assert len(challenge) >= 32
    assert verifier != challenge


def test_tool_id_and_arguments_normalization():
    assert _tool_id("Docs Server", "search knowledge") == "mcp__Docs_Server__search_knowledge"
    assert _normalize_arguments(None) == {}
    assert _normalize_arguments({"q": "x"}) == {"q": "x"}
    assert _normalize_arguments('{"q": "x"}') == {"q": "x"}
    assert _normalize_arguments("plain") == {"input": "plain"}


def test_usage_as_dicts():
    rows = usage_as_dicts(
        [
            McpUsageEvent(
                tenant_id="t1",
                run_key="r1",
                server_name="docs",
                tool_name="search",
                step="tool_call",
                ok=True,
            )
        ]
    )
    assert rows[0]["server_name"] == "docs"
    assert rows[0]["ok"] is True
