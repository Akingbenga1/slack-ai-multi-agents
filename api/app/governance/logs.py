"""Recent usage events + jobs for org logs viewer (Sprint 20.2)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.db.models import Job, UsageEvent


def list_usage_events(
    db: Session,
    tenant_id: UUID | str,
    *,
    event_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[UsageEvent], int]:
    """Newest-first usage_events for the tenant (mentions, tokens, jobs, …)."""
    tid = UUID(str(tenant_id))
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    filters = [UsageEvent.tenant_id == tid]
    if event_type:
        filters.append(UsageEvent.event_type == event_type.strip())
    total = db.scalar(select(func.count()).select_from(UsageEvent).where(*filters)) or 0
    q = (
        select(UsageEvent)
        .where(*filters)
        .order_by(UsageEvent.created_at.desc())
        .offset(off)
        .limit(lim)
    )
    return list(db.scalars(q).all()), int(total)


def list_jobs(
    db: Session,
    tenant_id: UUID | str,
    *,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Job], int]:
    """Newest-first jobs rows (errors when status=failed)."""
    tid = UUID(str(tenant_id))
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    filters = [Job.tenant_id == tid]
    if status:
        filters.append(Job.status == status.strip())
    total = db.scalar(select(func.count()).select_from(Job).where(*filters)) or 0
    q = (
        select(Job)
        .where(*filters)
        .order_by(Job.created_at.desc())
        .offset(off)
        .limit(lim)
    )
    return list(db.scalars(q).all()), int(total)


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
