"""Optional MCP process tenant binding (stdio / Inspector)."""

from __future__ import annotations

import os
from uuid import UUID

from api.app.qdrant.tenant import require_client_id


def bound_client_id() -> str | None:
    raw = (os.environ.get("MCP_BOUND_CLIENT_ID") or "").strip()
    return raw or None


def require_tool_client_id(client_id: str | None) -> str:
    """
    Require a non-blank client_id; when ``MCP_BOUND_CLIENT_ID`` is set, it must match.

    In-process agent calls are additionally checked by ``invoke_mcp`` against
    request/task context. This env bind protects stdio MCP from arbitrary tenant
    switching by tool args.
    """
    cid = require_client_id(client_id)
    bound = bound_client_id()
    if not bound:
        return cid
    try:
        if str(UUID(bound)) != str(UUID(cid)):
            raise PermissionError(
                f"MCP client_id {cid!r} does not match bound tenant {bound!r}"
            )
    except ValueError as exc:
        raise PermissionError(f"Invalid MCP bound/client id: {bound!r}/{cid!r}") from exc
    return cid


__all__ = ["bound_client_id", "require_tool_client_id"]
