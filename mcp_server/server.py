"""FastMCP factory — stdio process (no bundled tools).

All tool discovery is now DB-driven via the tool_registry table.
The MCP server is kept as an empty shell for external/stdio transport
compatibility; tools are registered in the database per tenant.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def create_mcp(*, name: str = "client-slack-agents") -> FastMCP:
    """Build an empty MCP server. Tools are discovered from the DB at runtime."""
    return FastMCP(name)


def main() -> None:
    """Entry: run over stdio (default). Ctrl+C / EOF stops the process."""
    create_mcp().run(transport="stdio")


if __name__ == "__main__":
    main()
