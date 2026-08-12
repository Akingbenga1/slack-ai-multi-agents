"""Celery Adapter for ``JobQueue`` (Sprint 38).

Owns ``apply_async`` and Celery task symbols. Product code never imports
Celery; Beat / HTTP call ``JobQueue.enqueue`` only.
"""

from __future__ import annotations

from typing import Any

from api.app.job_queue.types import EnqueueResult
from api.app.settings import Settings, get_settings
from worker.job_meta import (
    KIND_HEARTBEAT,
    KIND_INGEST_UPLOAD,
    KIND_RECURRING_REPORT,
    KIND_SLACK_HISTORY_SYNC,
)
from worker.queues import enqueue_options


class CeleryJobQueue:
    """Celery + Redis enqueue adapter (``REDIS_URL`` remains the broker)."""

    name = "celery"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def enqueue(
        self,
        *,
        kind: str,
        tenant_id: str,
        payload: dict[str, Any] | None = None,
    ) -> EnqueueResult:
        cid = str(tenant_id or "").strip()
        if not cid:
            raise ValueError("tenant_id is required")
        data = dict(payload or {})
        priority = int(data.get("priority", 0))
        opts = enqueue_options(client_id=cid, priority=priority)
        queue = str(opts["queue"])

        if kind == KIND_HEARTBEAT:
            from worker.tasks import heartbeat

            result = heartbeat.apply_async(
                kwargs={
                    "message": str(data.get("message") or "ok"),
                    "tenant_id": cid,
                    "priority": priority,
                },
                **opts,
            )
        elif kind == KIND_INGEST_UPLOAD:
            from worker.tasks import ingest_upload_task

            relative_path = str(data.get("relative_path") or "").strip()
            filename = str(data.get("filename") or "").strip()
            file_role = str(data.get("file_role") or "").strip()
            if not relative_path or not filename or not file_role:
                raise ValueError(
                    "ingest_upload requires relative_path, filename, file_role"
                )
            result = ingest_upload_task.apply_async(
                kwargs={
                    "relative_path": relative_path,
                    "filename": filename,
                    "file_role": file_role,
                    "tenant_id": cid,
                    "upload_id": data.get("upload_id"),
                    "channel": data.get("channel"),
                    "priority": priority,
                },
                **opts,
            )
        elif kind == KIND_SLACK_HISTORY_SYNC:
            from worker.tasks import slack_history_sync_task

            channel_ids = data.get("channel_ids")
            ids = list(channel_ids) if channel_ids is not None else None
            # Default bulk priority when omitted (-1 → low queue).
            if "priority" not in data:
                priority = -1
                opts = enqueue_options(client_id=cid, priority=priority)
                queue = str(opts["queue"])
            result = slack_history_sync_task.apply_async(
                kwargs={
                    "tenant_id": cid,
                    "channel_ids": ids,
                    "priority": priority,
                },
                **opts,
            )
        elif kind == KIND_RECURRING_REPORT:
            from worker.tasks import recurring_report_task

            result = recurring_report_task.apply_async(
                kwargs={
                    "tenant_id": cid,
                    "channel_id": data.get("channel_id"),
                    "window_label": data.get("window_label"),
                    "prefer_sync": bool(data.get("prefer_sync", True)),
                    "force": bool(data.get("force", False)),
                    "priority": priority,
                },
                **opts,
            )
        else:
            raise ValueError(f"Unknown job kind={kind!r}")

        return EnqueueResult(task_id=str(result.id), queue=queue, kind=kind)
