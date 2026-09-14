"""Local Bearer-authenticated MCP server for manual Org Rep testing.

Run: uv run python scripts/mock_auth_mcp_server.py
Listens on http://127.0.0.1:8765/mcp
Required header: Authorization: Bearer test-org-mcp-secret
"""

from __future__ import annotations

from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

EXPECTED_TOKEN = "test-org-mcp-secret"
HOST = "127.0.0.1"
PORT = 8765

mcp = FastMCP("org-auth-office")


@mcp.tool()
def office_finance_status(department: str = "finance") -> str:
    """Return a short finance status line that proves authenticated MCP ran."""
    dept = (department or "finance").strip() or "finance"
    return (
        f"AUTHENTICATED_MCP_OK: {dept} reports Q3 invoice packet is ready "
        "and waiting for Org Rep review."
    )


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        auth = request.headers.get("authorization") or ""
        if not auth.startswith("Bearer "):
            return JSONResponse(
                {"error": "missing bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = auth[len("Bearer ") :].strip()
        if token != EXPECTED_TOKEN:
            return JSONResponse(
                {"error": "invalid bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)


def main() -> None:
    # Use FastMCP's own ASGI app so its session-manager lifespan starts.
    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
    print(f"Authenticated MCP listening on http://{HOST}:{PORT}/mcp")
    print(f"Use Bearer token: {EXPECTED_TOKEN}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
