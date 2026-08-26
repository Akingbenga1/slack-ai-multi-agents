"""MCP server tests — empty server after bundled tool removal."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_server.server import create_mcp

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def mcp_session() -> AsyncGenerator[ClientSession, None]:
    app = create_mcp()
    async with create_connected_server_and_client_session(
        app, raise_exceptions=True
    ) as session:
        yield session


@pytest.mark.anyio
async def test_list_tools_empty(mcp_session: ClientSession):
    """After bundled tool removal, the MCP server exposes zero tools."""
    tools = await mcp_session.list_tools()
    assert len(tools.tools) == 0


@pytest.mark.anyio
async def test_create_mcp_returns_server():
    app = create_mcp()
    assert app is not None
