"""Celery tasks (heartbeat + knowledge upload ingest + Slack history sync)."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional, Sequence

from api.app.ingest.upload_ingest import ingest_upload
from api.app.logging_config import configure_logging
from api.app.membership import DEMO_TENANT_ID
from api.app.governance.usage import (
    EVENT_INGEST,
    EVENT_JOB,
    EVENT_REPORT_POST,
    EVENT_SYNC_RUN,
    record_usage,
)
from api.app.reports.post import post_recurring_report
from api.app.reports.schedule import list_tenants_for_scheduled_reports
from api.app.settings import get_settings
from api.app.slack.schedule import list_tenants_for_scheduled_slack_sync
from api.app.slack.sync import sync_slack_history
from api.app.tenant import get_client_id, set_client_id
from api.app.uploads.roles import FileRole
from worker.celery_app import celery_app
from worker.job_meta import (
    KIND_HEARTBEAT,
    KIND_INGEST_UPLOAD,
    KIND_RECURRING_REPORT,
    KIND_SLACK_HISTORY_SYNC,
    create_job,
    mark_failed,
    mark_running,
    mark_succeeded,
    session_scope,
)
from worker.queues import enqueue_options

configure_logging()
logger = logging.getLogger(__name__)


def _resolve_tenant_id(tenant_id: Optional[str]) -> uuid.UUID:
    client_id = get_client_id() or tenant_id
    if not client_id:
        client_id = str(DEMO_TENANT_ID)
        set_client_id(client_id)
    try:
        tenant_uuid = uuid.UUID(str(client_id))
    except ValueError as exc:
        raise ValueError(f"Invalid tenant_id/client_id: {client_id!r}") from exc
    set_client_id(str(tenant_uuid))
    return tenant_uuid


@celery_app.task(name="worker.heartbeat", bind=True)
def heartbeat(
    self,
    message: str = "ok",
    tenant_id: Optional[str] = None,
    priority: int = 0,
) -> dict[str, Any]:
    """
    Tenant heartbeat: log + persist a `jobs` row.

    Prefer `client_id` from Celery headers (Beat / API enqueue).
    `tenant_id` kwarg is a fallback (e.g. manual invoke).
    """
    tenant_uuid = _resolve_tenant_id(tenant_id)
    logger.info(
        "heartbeat start task_id=%s message=%s client_id=%s",
        self.request.id,
        message,
        tenant_uuid,
    )

    db = session_scope()
    job = None
    try:
        job = create_job(
            db,
            tenant_id=tenant_uuid,
            kind=KIND_HEARTBEAT,
            priority=priority,
            payload={"message": message, "celery_task_id": self.request.id},
        )
        mark_running(db, job)
        result = {
            "message": message,
            "client_id": str(tenant_uuid),
            "job_id": str(job.id),
            "task_id": self.request.id,
        }
        mark_succeeded(db, job, result=result)
        record_usage(
            db,
            tenant_uuid,
            EVENT_JOB,
            units=1,
            meta={"kind": KIND_HEARTBEAT, "job_id": str(job.id)},
            commit=True,
        )
        logger.info(
            "heartbeat ok job_id=%s status=succeeded client_id=%s",
            job.id,
            tenant_uuid,
        )
        return result
    except Exception as exc:
        if job is not None:
            mark_failed(db, job, str(exc))
        logger.exception("heartbeat failed")
        raise
    finally:
        db.close()


def enqueue_heartbeat(
    *,
    client_id: str,
    message: str = "ok",
    priority: int = 0,
) -> Any:
    """Enqueue heartbeat on the priority-mapped queue with tenant header."""
    return heartbeat.apply_async(
        kwargs={"message": message, "tenant_id": client_id, "priority": priority},
        **enqueue_options(client_id=client_id, priority=priority),
    )


@celery_app.task(name="worker.ingest_upload", bind=True)
def ingest_upload_task(
    self,
    *,
    relative_path: str,
    filename: str,
    file_role: str,
    tenant_id: Optional[str] = None,
    upload_id: Optional[str] = None,
    channel: Optional[str] = None,
    priority: int = 0,
) -> dict[str, Any]:
    """Parse a stored upload → chunk → TEI → Qdrant for one tenant."""
    tenant_uuid = _resolve_tenant_id(tenant_id)
    role = FileRole(file_role)
    logger.info(
        "ingest_upload start task_id=%s upload_id=%s role=%s file=%s client_id=%s",
        self.request.id,
        upload_id,
        role,
        filename,
        tenant_uuid,
    )

    db = session_scope()
    job = None
    try:
        job = create_job(
            db,
            tenant_id=tenant_uuid,
            kind=KIND_INGEST_UPLOAD,
            priority=priority,
            payload={
                "celery_task_id": self.request.id,
                "upload_id": upload_id,
                "relative_path": relative_path,
                "filename": filename,
                "file_role": str(role),
                "channel": channel,
            },
        )
        mark_running(db, job)
        ingest_result = ingest_upload(
            client_id=str(tenant_uuid),
            file_role=role,
            relative_path=relative_path,
            filename=filename,
            channel=channel,
        )
        result = {
            **ingest_result.as_dict(),
            "job_id": str(job.id),
            "task_id": self.request.id,
            "upload_id": upload_id,
        }
        mark_succeeded(db, job, result=result)
        record_usage(
            db,
            tenant_uuid,
            EVENT_INGEST,
            units=1,
            meta={
                "kind": KIND_INGEST_UPLOAD,
                "job_id": str(job.id),
                "upload_id": upload_id,
                "chunk_count": ingest_result.chunk_count,
            },
            commit=True,
        )
        logger.info(
            "ingest_upload ok job_id=%s chunks=%s client_id=%s",
            job.id,
            ingest_result.chunk_count,
            tenant_uuid,
        )
        return result
    except Exception as exc:
        if job is not None:
            mark_failed(db, job, str(exc))
        logger.exception("ingest_upload failed")
        raise
    finally:
        db.close()


def enqueue_ingest_upload(
    *,
    client_id: str,
    relative_path: str,
    filename: str,
    file_role: FileRole | str,
    upload_id: Optional[str] = None,
    channel: Optional[str] = None,
    priority: int = 0,
) -> Any:
    """Enqueue upload ingest with tenant Celery header."""
    return ingest_upload_task.apply_async(
        kwargs={
            "relative_path": relative_path,
            "filename": filename,
            "file_role": str(file_role),
            "tenant_id": client_id,
            "upload_id": upload_id,
            "channel": channel,
            "priority": priority,
        },
        **enqueue_options(client_id=client_id, priority=priority),
    )


@celery_app.task(name="worker.slack_history_sync", bind=True)
def slack_history_sync_task(
    self,
    *,
    tenant_id: Optional[str] = None,
    channel_ids: Optional[list[str]] = None,
    priority: int = 0,
) -> dict[str, Any]:
    """Incremental Slack history pull → WEB_API ingest → watermarks."""
    tenant_uuid = _resolve_tenant_id(tenant_id)
    logger.info(
        "slack_history_sync start task_id=%s client_id=%s channels=%s",
        self.request.id,
        tenant_uuid,
        channel_ids if channel_ids is not None else "all",
    )

    db = session_scope()
    job = None
    try:
        job = create_job(
            db,
            tenant_id=tenant_uuid,
            kind=KIND_SLACK_HISTORY_SYNC,
            priority=priority,
            payload={
                "celery_task_id": self.request.id,
                "channel_ids": channel_ids,
            },
        )
        mark_running(db, job)
        sync_result = sync_slack_history(
            db,
            tenant_id=tenant_uuid,
            channel_ids=channel_ids,
            settings=get_settings(),
        )
        result = {
            **sync_result.as_dict(),
            "job_id": str(job.id),
            "task_id": self.request.id,
        }
        mark_succeeded(db, job, result=result)
        record_usage(
            db,
            tenant_uuid,
            EVENT_SYNC_RUN,
            units=1,
            meta={
                "kind": KIND_SLACK_HISTORY_SYNC,
                "job_id": str(job.id),
                "message_count": sync_result.message_count,
                "chunk_count": sync_result.chunk_count,
            },
            commit=True,
        )
        logger.info(
            "slack_history_sync ok job_id=%s messages=%s chunks=%s client_id=%s",
            job.id,
            sync_result.message_count,
            sync_result.chunk_count,
            tenant_uuid,
        )
        return result
    except Exception as exc:
        if job is not None:
            mark_failed(db, job, str(exc))
        logger.exception("slack_history_sync failed")
        raise
    finally:
        db.close()


def enqueue_slack_history_sync(
    *,
    client_id: str,
    channel_ids: Optional[Sequence[str]] = None,
    priority: int = -1,
) -> Any:
    """Enqueue live Slack history sync (default low-priority bulk queue)."""
    ids = list(channel_ids) if channel_ids is not None else None
    return slack_history_sync_task.apply_async(
        kwargs={
            "tenant_id": client_id,
            "channel_ids": ids,
            "priority": priority,
        },
        **enqueue_options(client_id=client_id, priority=priority),
    )


@celery_app.task(name="worker.dispatch_slack_history_syncs", bind=True)
def dispatch_slack_history_syncs(self) -> dict[str, Any]:
    """
    Beat entrypoint: enqueue ``slack_history_sync`` for each due tenant.

    Due = has Slack install and ``schedules.slack_history_sync.enabled`` not false.
    On-demand API bypasses this gate.
    """
    db = session_scope()
    try:
        tenant_ids = list_tenants_for_scheduled_slack_sync(db)
        enqueued: list[dict[str, str]] = []
        for tenant_id in tenant_ids:
            client_id = str(tenant_id)
            async_result = enqueue_slack_history_sync(client_id=client_id)
            enqueued.append({"client_id": client_id, "task_id": async_result.id})
        logger.info(
            "dispatch_slack_history_syncs task_id=%s enqueued=%s",
            self.request.id,
            len(enqueued),
        )
        return {
            "task_id": self.request.id,
            "count": len(enqueued),
            "enqueued": enqueued,
        }
    finally:
        db.close()


@celery_app.task(name="worker.recurring_report", bind=True)
def recurring_report_task(
    self,
    *,
    tenant_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    window_label: Optional[str] = None,
    prefer_sync: bool = True,
    priority: int = 0,
) -> dict[str, Any]:
    """
    Generate a recurring digest and post it directly to the configured channel.

    Prefers a fresh Slack sync for the target channel before ``run_report``.
    No draft-approval gate.
    """
    tenant_uuid = _resolve_tenant_id(tenant_id)
    logger.info(
        "recurring_report start task_id=%s client_id=%s channel=%s",
        self.request.id,
        tenant_uuid,
        channel_id or "(from schedule)",
    )

    db = session_scope()
    job = None
    try:
        job = create_job(
            db,
            tenant_id=tenant_uuid,
            kind=KIND_RECURRING_REPORT,
            priority=priority,
            payload={
                "celery_task_id": self.request.id,
                "channel_id": channel_id,
                "window_label": window_label,
                "prefer_sync": prefer_sync,
            },
        )
        mark_running(db, job)
        post_result = post_recurring_report(
            db,
            tenant_id=tenant_uuid,
            channel_id=channel_id,
            window_label=window_label,
            prefer_sync=prefer_sync,
            settings=get_settings(),
            record_usage=True,
        )
        result = {
            **post_result,
            "job_id": str(job.id),
            "task_id": self.request.id,
        }
        mark_succeeded(db, job, result=result)
        record_usage(
            db,
            tenant_uuid,
            EVENT_REPORT_POST,
            units=1,
            meta={
                "kind": KIND_RECURRING_REPORT,
                "job_id": str(job.id),
                "channel_id": post_result.get("channel_id"),
                "hedge": post_result.get("hedge"),
            },
            commit=True,
        )
        logger.info(
            "recurring_report ok job_id=%s channel=%s client_id=%s",
            job.id,
            post_result.get("channel_id"),
            tenant_uuid,
        )
        return result
    except Exception as exc:
        if job is not None:
            mark_failed(db, job, str(exc))
            try:
                record_usage(
                    db,
                    tenant_uuid,
                    EVENT_JOB,
                    units=1,
                    meta={
                        "kind": KIND_RECURRING_REPORT,
                        "job_id": str(job.id),
                        "status": "failed",
                        "error": str(exc)[:500],
                    },
                    commit=True,
                )
            except Exception:
                logger.exception("recurring_report usage_record_failed")
        logger.exception("recurring_report failed")
        raise
    finally:
        db.close()


def enqueue_recurring_report(
    *,
    client_id: str,
    channel_id: Optional[str] = None,
    window_label: Optional[str] = None,
    prefer_sync: bool = True,
    priority: int = 0,
) -> Any:
    """Enqueue a forced or scheduled recurring report post."""
    return recurring_report_task.apply_async(
        kwargs={
            "tenant_id": client_id,
            "channel_id": channel_id,
            "window_label": window_label,
            "prefer_sync": prefer_sync,
            "priority": priority,
        },
        **enqueue_options(client_id=client_id, priority=priority),
    )


@celery_app.task(name="worker.dispatch_recurring_reports", bind=True)
def dispatch_recurring_reports(
    self,
    cadence: Optional[str] = None,
) -> dict[str, Any]:
    """
    Beat entrypoint: enqueue ``recurring_report`` for each due tenant.

    Due = Slack install + schedule enabled + channel_id set (+ optional cadence).
    On-demand API bypasses the enable gate.
    """
    db = session_scope()
    try:
        due = list_tenants_for_scheduled_reports(
            db,
            cadence=cadence if cadence in ("daily", "weekly") else None,
        )
        enqueued: list[dict[str, str]] = []
        for row in due:
            client_id = str(row["tenant_id"])
            async_result = enqueue_recurring_report(
                client_id=client_id,
                channel_id=row["channel_id"],
                window_label=row["window_label"],
                prefer_sync=True,
            )
            enqueued.append(
                {
                    "client_id": client_id,
                    "task_id": async_result.id,
                    "channel_id": row["channel_id"],
                    "cadence": row["cadence"],
                }
            )
        logger.info(
            "dispatch_recurring_reports task_id=%s cadence=%s enqueued=%s",
            self.request.id,
            cadence,
            len(enqueued),
        )
        return {
            "task_id": self.request.id,
            "cadence": cadence,
            "count": len(enqueued),
            "enqueued": enqueued,
        }
    finally:
        db.close()
