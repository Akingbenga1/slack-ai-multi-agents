"""Request/task-scoped tenant identity (`client_id`)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional
from uuid import UUID

CLIENT_ID_HEADER = "X-Client-Id"

_client_id_ctx: ContextVar[Optional[str]] = ContextVar("client_id", default=None)


def get_client_id() -> Optional[str]:
    return _client_id_ctx.get()


def set_client_id(client_id: Optional[str]) -> None:
    _client_id_ctx.set(_normalize(client_id))


def clear_client_id() -> None:
    _client_id_ctx.set(None)


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
