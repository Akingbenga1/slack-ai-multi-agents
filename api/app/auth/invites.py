"""Tokenised org-admin invites (Sprint 31.3). No SMTP; copy the magic-link URL."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.admin.actions import write_audit_log
from api.app.auth.tokens import create_access_token
from api.app.db.models import Invite, Membership, Role, Tenant, User
from api.app.membership import hash_password
from api.app.settings import Settings, get_settings

INVITE_TTL = timedelta(days=7)
INVITE_ROLE = "org_admin"


class InviteError(ValueError):
    """Invalid or unusable invite."""


@dataclass
class CreatedInvite:
    invite: Invite
    raw_token: str
    invite_url: str


@dataclass
class AcceptedInvite:
    user: User
    tenant: Tenant
    access_token: str


def hash_invite_token(raw: str, settings: Settings) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def invite_magic_link(raw_token: str, settings: Settings) -> str:
    base = (settings.web_app_url or "").rstrip("/")
    return f"{base}/invite?token={raw_token}"


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ensure_org_admin_role(db: Session) -> Role:
    role = db.scalar(select(Role).where(Role.name == INVITE_ROLE))
    if role is None:
        role = Role(name=INVITE_ROLE, description="Organisation admin — single tenant")
        db.add(role)
        db.flush()
    return role


def _lookup(db: Session, raw_token: str, settings: Settings) -> Invite | None:
    digest = hash_invite_token(raw_token.strip(), settings)
    return db.scalar(select(Invite).where(Invite.token_hash == digest))


def create_invite(
    db: Session,
    *,
    tenant_id: UUID | str,
    email: str,
    actor_user_id: UUID | str | None,
    actor_email: str | None,
    settings: Settings | None = None,
    ttl: timedelta = INVITE_TTL,
) -> CreatedInvite:
    settings = settings or get_settings()
    email_n = (email or "").strip().lower()
    if not email_n or "@" not in email_n or len(email_n) > 320:
        raise InviteError("email must be a valid email")

    tid = UUID(str(tenant_id))
    tenant = db.get(Tenant, tid)
    if tenant is None:
        raise InviteError("tenant not found")

    if db.scalar(select(User).where(User.email == email_n)) is not None:
        raise InviteError("email already exists")

    pending = db.scalar(
        select(Invite).where(
            Invite.tenant_id == tid,
            Invite.email == email_n,
            Invite.used_at.is_(None),
        )
    )
    if pending is not None and _as_utc(pending.expires_at) > datetime.now(timezone.utc):
        raise InviteError("a pending invite already exists for this email")

    raw = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    row = Invite(
        tenant_id=tid,
        email=email_n,
        role=INVITE_ROLE,
        token_hash=hash_invite_token(raw, settings),
        expires_at=now + ttl,
        created_by_user_id=UUID(str(actor_user_id)) if actor_user_id else None,
    )
    db.add(row)
    db.flush()
    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="invite.created",
        tenant_id=tid,
        detail={"email": email_n, "role": INVITE_ROLE},
    )
    db.commit()
    db.refresh(row)
    return CreatedInvite(
        invite=row,
        raw_token=raw,
        invite_url=invite_magic_link(raw, settings),
    )


def preview_invite(db: Session, *, token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    row = _lookup(db, token, settings)
    if row is None:
        raise InviteError("invite not found")
    now = datetime.now(timezone.utc)
    if row.used_at is not None:
        raise InviteError("invite already used")
    if _as_utc(row.expires_at) <= now:
        raise InviteError("invite expired")
    tenant = db.get(Tenant, row.tenant_id)
    return {
        "email": row.email,
        "role": row.role,
        "tenant_id": str(row.tenant_id),
        "tenant_name": tenant.name if tenant else None,
        "tenant_slug": tenant.slug if tenant else None,
        "expires_at": _as_utc(row.expires_at).isoformat(),
    }


def list_invites(db: Session, *, tenant_id: UUID | str) -> list[Invite]:
    tid = UUID(str(tenant_id))
    return list(
        db.scalars(
            select(Invite)
            .where(Invite.tenant_id == tid)
            .order_by(Invite.created_at.desc())
        ).all()
    )


def accept_invite(
    db: Session,
    *,
    token: str,
    password: str,
    display_name: str | None = None,
    settings: Settings | None = None,
) -> AcceptedInvite:
    """Join the existing tenant. Never creates a second organisation."""
    settings = settings or get_settings()
    password_n = (password or "").strip()
    if len(password_n) < 8:
        raise InviteError("password must be at least 8 characters")

    row = _lookup(db, token, settings)
    if row is None:
        raise InviteError("invite not found")
    now = datetime.now(timezone.utc)
    if row.used_at is not None:
        raise InviteError("invite already used")
    if _as_utc(row.expires_at) <= now:
        raise InviteError("invite expired")
    if row.role != INVITE_ROLE:
        raise InviteError("unsupported invite role")

    if db.scalar(select(User).where(User.email == row.email)) is not None:
        raise InviteError("email already exists")

    tenant = db.get(Tenant, row.tenant_id)
    if tenant is None:
        raise InviteError("tenant not found")

    role = _ensure_org_admin_role(db)
    user = User(
        email=row.email,
        display_name=(display_name or row.email).strip()[:255],
        hashed_password=hash_password(password_n),
        is_active=True,
    )
    db.add(user)
    db.flush()

    existing_memberships = db.scalars(
        select(Membership).where(Membership.user_id == user.id)
    ).all()
    if existing_memberships:
        raise InviteError("user already belongs to an organisation")

    db.add(
        Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
        )
    )
    row.used_at = now
    db.flush()
    write_audit_log(
        db,
        actor_user_id=user.id,
        actor_email=user.email,
        action="invite.accepted",
        tenant_id=tenant.id,
        detail={"invite_id": str(row.id), "email": user.email},
    )
    db.commit()
    db.refresh(user)
    db.refresh(tenant)

    token_jwt = create_access_token(
        settings=settings,
        sub=str(user.id),
        email=user.email,
        role="org_admin",
        tenant_id=str(tenant.id),
    )
    return AcceptedInvite(user=user, tenant=tenant, access_token=token_jwt)


def invite_public_row(row: Invite) -> dict:
    return {
        "id": str(row.id),
        "email": row.email,
        "role": row.role,
        "expires_at": _as_utc(row.expires_at).isoformat() if row.expires_at else None,
        "used_at": _as_utc(row.used_at).isoformat() if row.used_at else None,
        "created_at": _as_utc(row.created_at).isoformat() if row.created_at else None,
    }
