"""Slack live sync status for portal (last success/failure + watermarks)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.db.models import Job, SlackInstall, SyncWatermark
from api.app.slack.schedule import is_slack_history_sync_enabled
from api.app.slack.watermarks import SOURCE_SLACK_LIVE
from worker.job_meta import (
    KIND_SLACK_HISTORY_SYNC,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
)


@dataclass
class JobSnapshot:
    job_id: str
    status: str
    finished_at: Optional[datetime]
    error: Optional[str]
    result: Optional[dict[str, Any]]
    created_at: Optional[datetime]

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "error": self.error,
            "result": self.result,
        }


def _job_snapshot(job: Job | None) -> JobSnapshot | None:
    if job is None:
        return None
    return JobSnapshot(
        job_id=str(job.id),
        status=job.status,
        finished_at=job.finished_at,
        error=job.error,
        result=job.result if isinstance(job.result, dict) else None,
        created_at=job.created_at,
    )


def _latest_job(
    db: Session,
    *,
    tenant_id: UUID,
    status: str | None = None,
) -> Job | None:
    stmt = select(Job).where(
        Job.tenant_id == tenant_id,
        Job.kind == KIND_SLACK_HISTORY_SYNC,
    )
    if status is not None:
        stmt = stmt.where(Job.status == status)
    # Prefer finished_at, then created_at for in-flight rows.
    stmt = stmt.order_by(
        Job.finished_at.desc().nullslast(),
        Job.created_at.desc(),
    ).limit(1)
    return db.scalar(stmt)


def get_slack_history_sync_status(db: Session, tenant_id: UUID) -> dict[str, Any]:
    """Aggregate last success/failure, schedule flag, install, watermark freshness."""
    last_success = _job_snapshot(_latest_job(db, tenant_id=tenant_id, status=STATUS_SUCCEEDED))
    last_failure = _job_snapshot(_latest_job(db, tenant_id=tenant_id, status=STATUS_FAILED))
    last_job = _job_snapshot(_latest_job(db, tenant_id=tenant_id))

    install = db.scalar(select(SlackInstall).where(SlackInstall.tenant_id == tenant_id))
    channel_count = db.scalar(
        select(func.count())
        .select_from(SyncWatermark)
        .where(
            SyncWatermark.tenant_id == tenant_id,
            SyncWatermark.source == SOURCE_SLACK_LIVE,
        )
    )
    last_watermark_at = db.scalar(
        select(func.max(SyncWatermark.last_synced_at)).where(
            SyncWatermark.tenant_id == tenant_id,
            SyncWatermark.source == SOURCE_SLACK_LIVE,
        )
    )

    return {
        "client_id": str(tenant_id),
        "kind": KIND_SLACK_HISTORY_SYNC,
        "enabled": is_slack_history_sync_enabled(db, tenant_id),
        "slack_connected": install is not None,
        "last_success": last_success.as_dict() if last_success else None,
        "last_failure": last_failure.as_dict() if last_failure else None,
        "last_job": last_job.as_dict() if last_job else None,
        "watermarks": {
            "channel_count": int(channel_count or 0),
            "last_synced_at": last_watermark_at.isoformat() if last_watermark_at else None,
        },
    }
