"""Tenant membership listing and access removal for org admins."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from api.app.admin.actions import write_audit_log
from api.app.db.models import Invite, Membership, User


class MemberError(ValueError):
    """Invalid or blocked membership operation."""


@dataclass
class TenantMember:
    membership: Membership


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def list_tenant_members(db: Session, *, tenant_id: UUID | str) -> list[Membership]:
    tid = UUID(str(tenant_id))
    return list(
        db.scalars(
            select(Membership)
            .options(joinedload(Membership.user), joinedload(Membership.role))
            .where(Membership.tenant_id == tid)
            .order_by(Membership.created_at.asc())
        ).all()
    )


def member_public_row(row: Membership) -> dict:
    return {
        "user_id": str(row.user_id),
        "email": row.user.email,
        "display_name": row.user.display_name,
        "role": row.role.name,
        "joined_at": _as_utc(row.created_at).isoformat() if row.created_at else None,
        "is_active": bool(row.user.is_active),
    }


def remove_tenant_member(
    db: Session,
    *,
    tenant_id: UUID | str,
    user_id: UUID | str,
    actor_user_id: UUID | str | None,
    actor_email: str | None,
) -> None:
    tid = UUID(str(tenant_id))
    uid = UUID(str(user_id))
    actor_uid = UUID(str(actor_user_id)) if actor_user_id else None

    if actor_uid is not None and actor_uid == uid:
        raise MemberError("cannot remove your own access")

    row = db.scalar(
        select(Membership)
        .options(joinedload(Membership.user), joinedload(Membership.role))
        .where(Membership.tenant_id == tid, Membership.user_id == uid)
    )
    if row is None:
        raise MemberError("member not found")

    member_count = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.tenant_id == tid)
    )
    if member_count is not None and member_count <= 1:
        raise MemberError("cannot remove the last member")

    email = row.user.email
    db.delete(row)
    db.flush()
    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="member.removed",
        tenant_id=tid,
        detail={"user_id": str(uid), "email": email, "role": row.role.name},
    )
    db.commit()


def revoke_invite(
    db: Session,
    *,
    tenant_id: UUID | str,
    invite_id: UUID | str,
    actor_user_id: UUID | str | None,
    actor_email: str | None,
) -> None:
    tid = UUID(str(tenant_id))
    iid = UUID(str(invite_id))
    row = db.scalar(select(Invite).where(Invite.id == iid, Invite.tenant_id == tid))
    if row is None:
        raise MemberError("invite not found")
    if row.used_at is not None:
        raise MemberError("invite already used")

    email = row.email
    db.delete(row)
    db.flush()
    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="invite.revoked",
        tenant_id=tid,
        detail={"invite_id": str(iid), "email": email},
    )
    db.commit()
