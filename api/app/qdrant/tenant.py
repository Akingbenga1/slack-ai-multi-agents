"""Fail-closed tenant filter helpers for Qdrant."""

from __future__ import annotations

from qdrant_client.http import models

from api.app.qdrant.collection import CLIENT_ID_PAYLOAD_KEY
from api.app.tenant import ClientIdRequired, require_client_id as _require_client_id


class TenantFilterRequired(ClientIdRequired):
    """Raised when a Qdrant helper is called without a tenant `client_id`."""


def require_client_id(client_id: str | None) -> str:
    try:
        return _require_client_id(
            client_id,
            message="client_id is required for Qdrant operations (fail-closed)",
        )
    except ClientIdRequired as exc:
        if isinstance(exc, TenantFilterRequired):
            raise
        raise TenantFilterRequired(
            "client_id is required for Qdrant operations (fail-closed)"
        ) from exc


def tenant_filter(client_id: str | None) -> models.Filter:
    """Build a mandatory `client_id` payload pre-filter (fail-closed)."""
    cid = require_client_id(client_id)
    return models.Filter(
        must=[
            models.FieldCondition(
                key=CLIENT_ID_PAYLOAD_KEY,
                match=models.MatchValue(value=cid),
            )
        ]
    )
