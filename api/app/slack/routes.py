from __future__ import annotations

import json
from typing import Annotated, Any, Optional
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.db.models import Tenant
from api.app.db.session import get_db
from api.app.governance.rate_limit import check_tenant_rate_limit
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings
from api.app.slack.agent_reply import process_agent_reply
from api.app.slack.echo import should_reply
from api.app.slack.store import (
    get_bot_token,
    get_install_by_team,
    get_install_by_tenant,
    upsert_install,
)
from api.app.slack.verify import verify_slack_signature
from api.app.tenant import get_client_id, set_client_id

logger = get_logger("api.slack")

router = APIRouter(prefix="/slack", tags=["slack"])


def _resolve_tenant_id(principal: AuthPrincipal) -> UUID:
    return resolve_tenant_uuid_for_principal(principal)


def _install_url(settings: Settings, tenant_id: UUID) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/slack/install?tenant_id={tenant_id}"


def _portal_slack_redirect(
    settings: Settings,
    *,
    connected: bool = False,
    error: Optional[str] = None,
    team_id: Optional[str] = None,
) -> RedirectResponse:
    """Send browser OAuth back to the org portal Slack page."""
    base = settings.web_app_url.rstrip("/")
    params: dict[str, str] = {}
    if connected:
        params["connected"] = "1"
    if team_id:
        params["team"] = team_id
    if error:
        params["error"] = error
    qs = urlencode(params)
    url = f"{base}/app/slack" + (f"?{qs}" if qs else "")
    return RedirectResponse(url)

BOT_SCOPES = ",".join(
    [
        "app_mentions:read",
        "channels:history",
        "channels:read",
        "chat:write",
        "files:read",
        "files:write",
        "groups:history",
        "groups:read",
        "im:history",
        "im:read",
        "im:write",
        "team:read",
        "users:read",
    ]
)


@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> Any:
    """HTTP Events: signature verify, url_verification, mention/DM → LangGraph."""
    body = await verify_slack_signature(request, settings.slack_signing_secret)
    payload = json.loads(body.decode("utf-8"))

    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge", "")
        return PlainTextResponse(content=challenge)

    event = payload.get("event") or {}
    team_id = payload.get("team_id") or event.get("team")
    install = get_install_by_team(db, team_id) if team_id else None
    if install:
        set_client_id(str(install.tenant_id))
        logger.info(
            "slack_event type=%s team_id=%s",
            event.get("type"),
            team_id,
        )
        # Gateway RPM after tenant resolve. Return 200 (not 429) so Slack does not retry-storm.
        rl = check_tenant_rate_limit(str(install.tenant_id), settings=settings)
        if not rl.allowed:
            logger.warning(
                "slack_event_rate_limited team_id=%s tenant_id=%s",
                team_id,
                install.tenant_id,
            )
            return JSONResponse(content={"ok": True, "rate_limited": True})

    # Slack retries on slow/5xx — skip to avoid duplicate posts
    is_retry = bool(request.headers.get("X-Slack-Retry-Num"))
    if install and not is_retry and should_reply(event):
        channel = event.get("channel")
        if channel:
            try:
                token = get_bot_token(install, settings)
                # Ack fast; agent + postMessage run after response (Slack ~3s window)
                background_tasks.add_task(
                    process_agent_reply,
                    tenant_id=install.tenant_id,
                    bot_token=token,
                    event=dict(event),
                    team_id=str(team_id) if team_id else None,
                    settings=settings,
                )
            except Exception:
                logger.exception("slack_agent_enqueue_failed team_id=%s", team_id)

    return JSONResponse({"ok": True})


@router.get("/install")
def slack_install(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Annotated[UUID, Query(description="client_id / tenants.id to map this workspace")],
) -> RedirectResponse:
    if not settings.slack_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SLACK_CLIENT_ID not configured",
        )
    if db.get(Tenant, tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown tenant_id")

    redirect_uri = f"{settings.public_base_url.rstrip('/')}/slack/oauth/callback"
    params = {
        "client_id": settings.slack_client_id,
        "scope": BOT_SCOPES,
        "redirect_uri": redirect_uri,
        "state": str(tenant_id),
    }
    url = f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/oauth/callback")
def slack_oauth_callback(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[Optional[str], Query()] = None,
    state: Annotated[Optional[str], Query()] = None,
    error: Annotated[Optional[str], Query()] = None,
) -> RedirectResponse:
    """Exchange OAuth code and redirect the browser back to the org portal."""
    if error:
        return _portal_slack_redirect(settings, error=f"Slack OAuth error: {error}")
    if not code or not state:
        return _portal_slack_redirect(settings, error="Missing code or state")
    if not settings.slack_client_id or not settings.slack_client_secret:
        return _portal_slack_redirect(
            settings, error="Slack OAuth credentials not configured"
        )

    try:
        tenant_id = UUID(state)
    except ValueError:
        return _portal_slack_redirect(settings, error="Invalid state")

    redirect_uri = f"{settings.public_base_url.rstrip('/')}/slack/oauth/callback"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": settings.slack_client_id,
                    "client_secret": settings.slack_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 — surface to portal
        logger.exception("slack_oauth_http_failed")
        return _portal_slack_redirect(settings, error=f"OAuth request failed: {exc}")

    if not data.get("ok"):
        return _portal_slack_redirect(
            settings, error=f"oauth.v2.access failed: {data.get('error')}"
        )

    team = data.get("team") or {}
    team_id = team.get("id")
    bot_token = (data.get("access_token") or "").strip()
    if not team_id or not bot_token:
        return _portal_slack_redirect(settings, error="Missing team or bot token")

    try:
        row = upsert_install(
            db,
            settings=settings,
            tenant_id=tenant_id,
            team_id=team_id,
            team_name=team.get("name"),
            bot_token=bot_token,
            authed_user_id=(data.get("authed_user") or {}).get("id"),
            scopes=data.get("scope"),
            raw={"ok": True, "team": team, "scope": data.get("scope"), "app_id": data.get("app_id")},
        )
    except ValueError as exc:
        return _portal_slack_redirect(settings, error=str(exc))

    logger.info("slack_install saved team_id=%s tenant_id=%s", team_id, tenant_id)
    return _portal_slack_redirect(
        settings, connected=True, team_id=row.team_id
    )


@router.get("/connection")
def slack_connection(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Org portal: Slack install status for the current tenant (OR-08)."""
    tid = _resolve_tenant_id(principal)
    row = get_install_by_tenant(db, tid)
    install_url = _install_url(settings, tid)
    if row is None:
        return {
            "connected": False,
            "client_id": str(tid),
            "team_id": None,
            "team_name": None,
            "scopes": None,
            "installed_at": None,
            "install_url": install_url,
            "slack_configured": bool(settings.slack_client_id),
        }
    return {
        "connected": True,
        "client_id": str(tid),
        "team_id": row.team_id,
        "team_name": row.team_name,
        "scopes": row.scopes,
        "installed_at": row.installed_at.isoformat() if row.installed_at else None,
        "install_url": install_url,
        "slack_configured": bool(settings.slack_client_id),
    }


@router.get("/installs/{team_id}")
def get_install(
    team_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Lookup install mapping (no token returned)."""
    row = get_install_by_team(db, team_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Install not found")
    return {
        "team_id": row.team_id,
        "team_name": row.team_name,
        "client_id": str(row.tenant_id),
        "scopes": row.scopes,
        "installed_at": row.installed_at.isoformat() if row.installed_at else None,
    }
