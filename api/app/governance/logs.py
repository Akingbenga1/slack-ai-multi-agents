"""Recent usage events + jobs for org logs viewer (Sprint 20.2)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import Job, UsageEvent


def list_usage_events(
    db: Session,
    tenant_id: UUID | str,
    *,
    event_type: Optional[str] = None,
    limit: int = 50,
) -> list[UsageEvent]:
    """Newest-first usage_events for the tenant (mentions, tokens, jobs, …)."""
    tid = UUID(str(tenant_id))
    lim = max(1, min(int(limit), 200))
    q = (
        select(UsageEvent)
        .where(UsageEvent.tenant_id == tid)
        .order_by(UsageEvent.created_at.desc())
        .limit(lim)
    )
    if event_type:
        q = q.where(UsageEvent.event_type == event_type.strip())
    return list(db.scalars(q).all())


def list_jobs(
    db: Session,
    tenant_id: UUID | str,
    *,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[Job]:
    """Newest-first jobs rows (errors when status=failed)."""
    tid = UUID(str(tenant_id))
    lim = max(1, min(int(limit), 200))
    q = (
        select(Job)
        .where(Job.tenant_id == tid)
        .order_by(Job.created_at.desc())
        .limit(lim)
    )
    if status:
        q = q.where(Job.status == status.strip())
    return list(db.scalars(q).all())


def serialize_usage_event(row: UsageEvent) -> dict:
    return {
        "id": str(row.id),
        "event_type": row.event_type,
        "units": int(row.units or 0),
        "meta": row.meta or {},
        "created_at": row.created_at.isoformat().replace("+00:00", "Z")
        if row.created_at
        else None,
    }


def serialize_job(row: Job) -> dict:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "status": row.status,
        "error": row.error,
        "created_at": row.created_at.isoformat().replace("+00:00", "Z")
        if row.created_at
        else None,
        "finished_at": row.finished_at.isoformat().replace("+00:00", "Z")
        if row.finished_at
        else None,
    }
