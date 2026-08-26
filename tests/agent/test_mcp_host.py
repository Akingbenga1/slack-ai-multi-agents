"""Unit tests for MCP host readiness helpers."""

from __future__ import annotations

import pytest

from api.app.agent.mcp_host import (
    check_mcp_server,
    extract_http_url,
    extract_stdio_launch,
)


def test_extract_http_url_from_remotes():
    url = extract_http_url(
        {
            "remotes": [
                {"type": "streamable-http", "url": "https://mcp.example/v1"},
            ]
        }
    )
    assert url == "https://mcp.example/v1"


def test_extract_stdio_launch():
    launch = extract_stdio_launch(
        {"command": "npx", "args": ["-y", "demo-mcp"], "env": {"A": "1"}}
    )
    assert launch is not None
    command, args, env = launch
    assert command == "npx"
    assert args == ["-y", "demo-mcp"]
    assert env == {"A": "1"}


def test_call_registered_mcp_tool_disabled():
    from api.app.agent.mcp_host import McpHostError, call_registered_mcp_tool

    with pytest.raises(McpHostError) as exc:
        call_registered_mcp_tool(
            server_name="off",
            transport="http",
            connection_config={"url": "https://example.com/mcp"},
            enabled=False,
            tool_name="any",
            arguments={},
        )
    assert exc.value.code == "server_disabled"


def test_check_mcp_server_disabled():
    result = check_mcp_server(
        server_name="x",
        transport="http",
        connection_config={"url": "https://example.com"},
        enabled=False,
    )
    assert result.ready is False
    assert result.enabled is False


def test_check_mcp_server_stdio_missing_command():
    result = check_mcp_server(
        server_name="x",
        transport="stdio",
        connection_config={},
        enabled=True,
    )
    assert result.ready is False
    assert "missing command" in (result.error or "")
