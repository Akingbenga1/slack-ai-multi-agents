"""Platform health + recent error rates (Sprint 21.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.db.models import Job, UsageEvent
from api.app.health import run_deep_health
from api.app.settings import Settings
from worker.job_meta import STATUS_FAILED


def _window_start(hours: int = 24) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def job_error_rates(db: Session, *, hours: int = 24) -> dict[str, Any]:
    """Failed vs total jobs in the window (all tenants)."""
    since = _window_start(hours)
    total = db.scalar(
        select(func.count()).select_from(Job).where(Job.created_at >= since)
    )
    failed = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.created_at >= since, Job.status == STATUS_FAILED)
    )
    total_i = int(total or 0)
    failed_i = int(failed or 0)
    by_kind_rows = db.execute(
        select(Job.kind, func.count())
        .where(Job.created_at >= since, Job.status == STATUS_FAILED)
        .group_by(Job.kind)
        .order_by(func.count().desc())
    ).all()
    return {
        "window_hours": hours,
        "since": since.isoformat(),
        "jobs_total": total_i,
        "jobs_failed": failed_i,
        "failure_rate": (failed_i / total_i) if total_i else 0.0,
        "failed_by_kind": [
            {"kind": kind, "count": int(count)} for kind, count in by_kind_rows
        ],
    }


def usage_event_counts(db: Session, *, hours: int = 24) -> dict[str, Any]:
    since = _window_start(hours)
    rows = db.execute(
        select(UsageEvent.event_type, func.count())
        .where(UsageEvent.created_at >= since)
        .group_by(UsageEvent.event_type)
        .order_by(func.count().desc())
    ).all()
    return {
        "window_hours": hours,
        "since": since.isoformat(),
        "by_type": [
            {"event_type": et, "count": int(count)} for et, count in rows
        ],
    }


def platform_health_overview(
    db: Session,
    settings: Settings,
    *,
    hours: int = 24,
) -> dict[str, Any]:
    deep = run_deep_health(settings)
    return {
        "status": deep["status"],
        "checks": deep["checks"],
        "errors": job_error_rates(db, hours=hours),
        "usage": usage_event_counts(db, hours=hours),
    }
