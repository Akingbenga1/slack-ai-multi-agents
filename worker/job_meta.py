"""Persist Celery run metadata in Postgres `jobs`."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from api.app.db.models import Job
from api.app.db.session import SessionLocal

KIND_HEARTBEAT = "heartbeat"
KIND_INGEST_UPLOAD = "ingest_upload"
KIND_SLACK_HISTORY_SYNC = "slack_history_sync"
KIND_RECURRING_REPORT = "recurring_report"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_job(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    kind: str,
    priority: int = 0,
    payload: Optional[dict[str, Any]] = None,
) -> Job:
    job = Job(
        tenant_id=tenant_id,
        kind=kind,
        status=STATUS_PENDING,
        priority=priority,
        payload=payload,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_running(db: Session, job: Job) -> Job:
    job.status = STATUS_RUNNING
    job.started_at = _utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_succeeded(db: Session, job: Job, result: Optional[dict[str, Any]] = None) -> Job:
    job.status = STATUS_SUCCEEDED
    job.result = result
    job.error = None
    job.finished_at = _utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_failed(db: Session, job: Job, error: str) -> Job:
    job.status = STATUS_FAILED
    job.error = error[:4000]
    job.finished_at = _utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def session_scope() -> Session:
    """Caller must close (or use as context via try/finally)."""
    return SessionLocal()
