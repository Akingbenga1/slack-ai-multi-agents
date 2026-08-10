"""Persist Slack installs: team_id → tenant (client_id)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import SlackInstall, Tenant
from api.app.settings import Settings
from api.app.slack.crypto import decrypt_bot_token, encrypt_bot_token


def get_install_by_team(db: Session, team_id: str) -> Optional[SlackInstall]:
    return db.scalar(select(SlackInstall).where(SlackInstall.team_id == team_id))


def get_install_by_tenant(db: Session, tenant_id: UUID) -> Optional[SlackInstall]:
    """Return one install for the tenant (MVP: one workspace per tenant)."""
    return db.scalar(
        select(SlackInstall)
        .where(SlackInstall.tenant_id == tenant_id)
        .order_by(SlackInstall.installed_at.desc())
        .limit(1)
    )


def get_bot_token(install: SlackInstall, settings: Settings) -> str:
    if not install.bot_token_encrypted:
        raise ValueError("Install has no bot token")
    return decrypt_bot_token(install.bot_token_encrypted, settings)


def upsert_install(
    db: Session,
    *,
    settings: Settings,
    tenant_id: UUID,
    team_id: str,
    team_name: Optional[str],
    bot_token: str,
    authed_user_id: Optional[str],
    scopes: Optional[str],
    raw: Optional[dict[str, Any]] = None,
    commit: bool = True,
) -> SlackInstall:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError(f"Unknown tenant_id={tenant_id}")

    encrypted = encrypt_bot_token(bot_token, settings)
    row = get_install_by_team(db, team_id)
    if row is None:
        row = SlackInstall(
            tenant_id=tenant_id,
            team_id=team_id,
            team_name=team_name,
            bot_token_encrypted=encrypted,
            authed_user_id=authed_user_id,
            scopes=scopes,
            raw=raw,
        )
        db.add(row)
    else:
        row.tenant_id = tenant_id
        row.team_name = team_name
        row.bot_token_encrypted = encrypted
        row.authed_user_id = authed_user_id
        row.scopes = scopes
        row.raw = raw
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row
