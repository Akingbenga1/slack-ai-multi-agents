"""Ingest upload job status for the org portal (Sprint 19.2)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import Job
from worker.job_meta import KIND_INGEST_UPLOAD


def _job_dict(job: Job) -> dict[str, Any]:
    payload = job.payload if isinstance(job.payload, dict) else {}
    result = job.result if isinstance(job.result, dict) else None
    return {
        "job_id": str(job.id),
        "client_id": str(job.tenant_id),
        "kind": job.kind,
        "status": job.status,
        "upload_id": payload.get("upload_id"),
        "filename": payload.get("filename"),
        "file_role": payload.get("file_role"),
        "celery_task_id": payload.get("celery_task_id"),
        "error": job.error,
        "result": result,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def list_ingest_jobs(
    db: Session,
    tenant_id: UUID,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Recent ingest_upload jobs for one tenant (newest first)."""
    lim = max(1, min(int(limit), 100))
    rows = db.scalars(
        select(Job)
        .where(
            Job.tenant_id == tenant_id,
            Job.kind == KIND_INGEST_UPLOAD,
        )
        .order_by(Job.created_at.desc())
        .limit(lim)
    ).all()
    return [_job_dict(j) for j in rows]


def get_ingest_job_by_upload_id(
    db: Session,
    tenant_id: UUID,
    upload_id: str,
) -> Optional[dict[str, Any]]:
    """Latest ingest job whose payload.upload_id matches."""
    uid = (upload_id or "").strip()
    if not uid:
        return None
    rows = db.scalars(
        select(Job)
        .where(
            Job.tenant_id == tenant_id,
            Job.kind == KIND_INGEST_UPLOAD,
        )
        .order_by(Job.created_at.desc())
        .limit(50)
    ).all()
    for job in rows:
        payload = job.payload if isinstance(job.payload, dict) else {}
        if str(payload.get("upload_id") or "") == uid:
            return _job_dict(job)
    return None


__all__ = [
    "get_ingest_job_by_upload_id",
    "list_ingest_jobs",
]
