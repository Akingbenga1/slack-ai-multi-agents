"""Signed Slack OAuth state tokens — bind install flow to an authenticated principal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt

from api.app.settings import Settings

_SLACK_OAUTH_PURPOSE = "slack_oauth"
_TTL_MINUTES = 15


def create_slack_oauth_state(
    *,
    settings: Settings,
    tenant_id: UUID | str,
    actor_sub: str,
) -> str:
    """Mint a short-lived signed state for Slack OAuth start/callback."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "purpose": _SLACK_OAUTH_PURPOSE,
        "tenant_id": str(tenant_id),
        "sub": str(actor_sub),
        "iat": now,
        "exp": now + timedelta(minutes=_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_slack_oauth_state(state: str, settings: Settings) -> tuple[str, str]:
    """
    Verify Slack OAuth ``state`` and return ``(tenant_id, actor_sub)``.

    Raises ``ValueError`` when invalid or expired.
    """
    raw = (state or "").strip()
    if not raw:
        raise ValueError("missing_oauth_state")
    try:
        payload = jwt.decode(raw, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ValueError("invalid_oauth_state") from exc

    if payload.get("purpose") != _SLACK_OAUTH_PURPOSE:
        raise ValueError("invalid_oauth_state")

    tenant_id = str(payload.get("tenant_id") or "").strip()
    actor_sub = str(payload.get("sub") or "").strip()
    if not tenant_id or not actor_sub:
        raise ValueError("invalid_oauth_state")

    try:
        UUID(tenant_id)
    except ValueError as exc:
        raise ValueError("invalid_oauth_state") from exc

    return tenant_id, actor_sub


__all__ = ["create_slack_oauth_state", "verify_slack_oauth_state"]
