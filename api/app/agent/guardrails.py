"""Agent guardrails — tenant filter must never be dropped."""

from __future__ import annotations

from api.app.tenant import ClientIdRequired
from api.app.tenant import require_client_id as _require_client_id


class TenantContextRequired(ClientIdRequired):
    """Raised when agent state is missing a usable client_id."""


def require_tenant_client_id(client_id: str | None, *, where: str = "agent") -> str:
    """Fail-closed: every agent node must carry a non-empty tenant id."""
    try:
        return _require_client_id(client_id, where=where)
    except ClientIdRequired as exc:
        if isinstance(exc, TenantContextRequired):
            raise
        raise TenantContextRequired(
            f"client_id is required for {where} (tenant filter must never be dropped)"
        ) from exc
