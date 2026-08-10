"""Request/task-scoped tenant identity (`client_id`)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional
from uuid import UUID

CLIENT_ID_HEADER = "X-Client-Id"

_client_id_ctx: ContextVar[Optional[str]] = ContextVar("client_id", default=None)


class ClientIdRequired(ValueError):
    """Raised when a tenant-scoped operation lacks a usable ``client_id``."""


def get_client_id() -> Optional[str]:
    return _client_id_ctx.get()


def set_client_id(client_id: Optional[str]) -> None:
    _client_id_ctx.set(_normalize(client_id))


def clear_client_id() -> None:
    _client_id_ctx.set(None)


def require_client_id(
    client_id: Optional[str],
    *,
    where: str = "operation",
    message: Optional[str] = None,
) -> str:
    """
    Fail-closed: every tenant-scoped helper must receive a non-empty client_id.

    Domain modules may catch ``ClientIdRequired`` and re-raise with a local
    message / subtype; do not duplicate the empty-check logic.
    """
    value = str(client_id).strip() if client_id is not None else ""
    if not value:
        raise ClientIdRequired(
            message or f"client_id is required for {where}"
        )
    return value


def require_tenant_client_id(
    client_id: Optional[str],
    *,
    where: str = "agent",
) -> str:
    """Alias of ``require_client_id`` (agent / guardrail call sites)."""
    return require_client_id(client_id, where=where)


def _normalize(client_id: Optional[str]) -> Optional[str]:
    if client_id is None:
        return None
    value = client_id.strip()
    if not value:
        return None
    # Accept UUID strings; keep other non-empty slugs for early scaffolding
    try:
        return str(UUID(value))
    except ValueError:
        return value
