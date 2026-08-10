"""Celery tasks (heartbeat + knowledge upload ingest + Slack history sync)."""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from api.app.ingest.upload_ingest import ingest_upload
from api.app.logging_config import configure_logging
from api.app.governance.usage import (
    EVENT_INGEST,
    EVENT_JOB,
    EVENT_REPORT_POST,
    EVENT_SYNC_RUN,
)
from api.app.reports.post import post_recurring_report
from api.app.schedules import (
    SLACK_HISTORY_SYNC_KEY,
    list_due_for_kind,
    list_due_recurring_reports,
)
from api.app.settings import get_settings
from api.app.slack.sync import sync_slack_history
from api.app.uploads.roles import FileRole
from worker.celery_app import celery_app
from worker.job_meta import (
    KIND_HEARTBEAT,
    KIND_INGEST_UPLOAD,
    KIND_RECURRING_REPORT,
    KIND_SLACK_HISTORY_SYNC,
)
from worker.queues import enqueue_options
from worker.tenant_job import (
    TenantJobContext,
    resolve_tenant_id,
    run_dispatch,
    tenant_job,
)

configure_logging()
logger = logging.getLogger(__name__)

# Re-export for tests that monkeypatch worker.tasks._resolve_tenant_id
_resolve_tenant_id = resolve_tenant_id


@celery_app.task(name="worker.heartbeat", bind=True)
@tenant_job(kind=KIND_HEARTBEAT, usage_event=EVENT_JOB, log_label="heartbeat")
def heartbeat(
    self,
    ctx: TenantJobContext,
    message: str = "ok",
    tenant_id: Optional[str] = None,
    priority: int = 0,
) -> dict[str, Any]:
    """
    Tenant heartbeat: log + persist a `jobs` row.

    Prefer `client_id` from Celery headers (Beat / API enqueue).
    `tenant_id` kwarg is a fallback (e.g. manual invoke).
    """
    ctx.set_usage(meta={"kind": KIND_HEARTBEAT, "job_id": str(ctx.job.id)})
    return {
        "message": message,
        "client_id": str(ctx.tenant_id),
    }


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
@tenant_job(
    kind=KIND_INGEST_UPLOAD,
    usage_event=EVENT_INGEST,
    log_label="ingest_upload",
)
def ingest_upload_task(
    self,
    ctx: TenantJobContext,
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
    role = FileRole(file_role)
    logger.info(
        "ingest_upload role=%s file=%s upload_id=%s",
        role,
        filename,
        upload_id,
    )
    ingest_result = ingest_upload(
        client_id=str(ctx.tenant_id),
        file_role=role,
        relative_path=relative_path,
        filename=filename,
        channel=channel,
    )
    ctx.set_usage(
        meta={
            "kind": KIND_INGEST_UPLOAD,
            "job_id": str(ctx.job.id),
            "upload_id": upload_id,
            "chunk_count": ingest_result.chunk_count,
        }
    )
    return {
        **ingest_result.as_dict(),
        "upload_id": upload_id,
    }


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
@tenant_job(
    kind=KIND_SLACK_HISTORY_SYNC,
    usage_event=EVENT_SYNC_RUN,
    log_label="slack_history_sync",
)
def slack_history_sync_task(
    self,
    ctx: TenantJobContext,
    *,
    tenant_id: Optional[str] = None,
    channel_ids: Optional[list[str]] = None,
    priority: int = 0,
) -> dict[str, Any]:
    """Incremental Slack history pull → WEB_API ingest → watermarks."""
    logger.info(
        "slack_history_sync channels=%s",
        channel_ids if channel_ids is not None else "all",
    )
    sync_result = sync_slack_history(
        ctx.db,
        tenant_id=ctx.tenant_id,
        channel_ids=channel_ids,
        settings=get_settings(),
    )
    ctx.set_usage(
        meta={
            "kind": KIND_SLACK_HISTORY_SYNC,
            "job_id": str(ctx.job.id),
            "message_count": sync_result.message_count,
            "chunk_count": sync_result.chunk_count,
        }
    )
    logger.info(
        "slack_history_sync messages=%s chunks=%s",
        sync_result.message_count,
        sync_result.chunk_count,
    )
    return sync_result.as_dict()


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
    return run_dispatch(
        self,
        list_due=lambda db: list_due_for_kind(db, SLACK_HISTORY_SYNC_KEY),
        enqueue_row=lambda tenant_id: {
            "client_id": str(tenant_id),
            "task_id": enqueue_slack_history_sync(client_id=str(tenant_id)).id,
        },
        log_label="dispatch_slack_history_syncs",
    )


@celery_app.task(name="worker.recurring_report", bind=True)
@tenant_job(
    kind=KIND_RECURRING_REPORT,
    usage_event=EVENT_REPORT_POST,
    fail_usage_event=EVENT_JOB,
    log_label="recurring_report",
)
def recurring_report_task(
    self,
    ctx: TenantJobContext,
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
    logger.info(
        "recurring_report channel=%s",
        channel_id or "(from schedule)",
    )
    post_result = post_recurring_report(
        ctx.db,
        tenant_id=ctx.tenant_id,
        channel_id=channel_id,
        window_label=window_label,
        prefer_sync=prefer_sync,
        settings=get_settings(),
        record_usage=True,
    )
    ctx.set_usage(
        meta={
            "kind": KIND_RECURRING_REPORT,
            "job_id": str(ctx.job.id),
            "channel_id": post_result.get("channel_id"),
            "hedge": post_result.get("hedge"),
        }
    )
    logger.info(
        "recurring_report channel=%s",
        post_result.get("channel_id"),
    )
    return post_result


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
    cadence_filter = cadence if cadence in ("daily", "weekly") else None

    def enqueue_row(row: dict[str, Any]) -> dict[str, str]:
        client_id = str(row["tenant_id"])
        async_result = enqueue_recurring_report(
            client_id=client_id,
            channel_id=row["channel_id"],
            window_label=row["window_label"],
            prefer_sync=True,
        )
        return {
            "client_id": client_id,
            "task_id": async_result.id,
            "channel_id": row["channel_id"],
            "cadence": row["cadence"],
        }

    return run_dispatch(
        self,
        list_due=lambda db: list_due_recurring_reports(db, cadence=cadence_filter),
        enqueue_row=enqueue_row,
        log_label="dispatch_recurring_reports",
        extra={"cadence": cadence},
    )
