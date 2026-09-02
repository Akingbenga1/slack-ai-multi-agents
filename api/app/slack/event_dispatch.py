"""Shared Slack event dispatch for HTTP Events and Socket Mode transports."""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.db.session import SessionLocal
from api.app.governance.rate_limit import check_tenant_rate_limit
from api.app.logging_config import get_logger
from api.app.settings import Settings
from api.app.slack.agent_reply import process_agent_reply
from api.app.slack.echo import should_reply
from api.app.slack.store import get_bot_token, get_install_by_team
from api.app.tenant import set_client_id

logger = get_logger("api.slack.event_dispatch")

ReplyFn = Callable[..., dict[str, Any]]


def resolve_team_id(payload: dict[str, Any], event: dict[str, Any]) -> str | None:
    """Extract workspace team id from an Events API envelope."""
    raw = payload.get("team_id") or event.get("team") or payload.get("team", {}).get("id")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def should_process_slack_event(
    *,
    event: dict[str, Any],
    team_id: str | None,
    db: Session,
    settings: Settings,
    is_retry: bool = False,
) -> tuple[bool, str | None, UUID | None]:
    """
    Resolve install + entitlement pre-checks shared by HTTP and Socket Mode.

    Returns (allowed, skip_reason, tenant_id).
    """
    if is_retry:
        return False, "retry", None
    if not team_id:
        return False, "no_team", None
    if not should_reply(event):
        return False, "not_replyable", None

    install = get_install_by_team(db, team_id)
    if install is None:
        return False, "no_install", None

    set_client_id(str(install.tenant_id))
    rl = check_tenant_rate_limit(str(install.tenant_id), settings=settings)
    if not rl.allowed:
        logger.warning(
            "slack_event_rate_limited team_id=%s tenant_id=%s",
            team_id,
            install.tenant_id,
        )
        return False, "rate_limited", install.tenant_id

    channel = event.get("channel")
    if not channel:
        return False, "no_channel", install.tenant_id

    return True, None, install.tenant_id


def enqueue_agent_reply_for_event(
    *,
    event: dict[str, Any],
    team_id: str | None,
    settings: Settings,
    db: Session,
    is_retry: bool = False,
    background: ReplyFn | None = None,
) -> dict[str, Any]:
    """
    Gate mention/DM events and run the reply pipeline.

    ``background`` receives ``process_agent_reply`` kwargs when set (HTTP path).
    When omitted, spawns a daemon thread (Socket Mode path).
    """
    allowed, skip_reason, tenant_id = should_process_slack_event(
        event=event,
        team_id=team_id,
        db=db,
        settings=settings,
        is_retry=is_retry,
    )
    if not allowed:
        return {"ok": True, "skipped": True, "reason": skip_reason}

    assert tenant_id is not None
    install = get_install_by_team(db, team_id)
    if install is None:
        return {"ok": True, "skipped": True, "reason": "no_install"}

    try:
        token = get_bot_token(install, settings)
    except Exception:
        logger.exception("slack_bot_token_failed team_id=%s", team_id)
        return {"ok": False, "reason": "token_error"}

    kwargs: dict[str, Any] = {
        "tenant_id": install.tenant_id,
        "bot_token": token,
        "event": dict(event),
        "team_id": team_id,
        "settings": settings,
    }

    if background is not None:
        background(**kwargs)
        return {"ok": True, "queued": True}

    thread = threading.Thread(
        target=_run_agent_reply_safe,
        kwargs=kwargs,
        daemon=True,
        name=f"slack-reply-{team_id}",
    )
    thread.start()
    return {"ok": True, "queued": True}


def dispatch_events_api_payload(
    payload: dict[str, Any],
    *,
    settings: Settings,
    is_retry: bool = False,
    background: ReplyFn | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Handle one Events API envelope (HTTP or Socket Mode)."""
    if payload.get("type") != "event_callback":
        return {"ok": True, "skipped": True, "reason": "not_event_callback"}

    event = payload.get("event") or {}
    team_id = resolve_team_id(payload, event)
    logger.info(
        "slack_event type=%s team_id=%s transport=%s",
        event.get("type"),
        team_id,
        settings.slack_events_transport,
    )

    owns_db = db is None
    session = db or SessionLocal()
    try:
        return enqueue_agent_reply_for_event(
            event=event,
            team_id=team_id,
            settings=settings,
            db=session,
            is_retry=is_retry,
            background=background,
        )
    finally:
        if owns_db:
            session.close()


def _run_agent_reply_safe(**kwargs: Any) -> None:
    try:
        process_agent_reply(**kwargs)
    except Exception:
        logger.exception(
            "slack_agent_reply_failed tenant_id=%s",
            kwargs.get("tenant_id"),
        )
