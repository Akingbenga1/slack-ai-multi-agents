"""Celery application — Redis broker/backend, Beat schedule, tenant headers."""

from __future__ import annotations

from typing import Any

from celery import Celery
from celery.signals import before_task_publish, task_postrun, task_prerun

from api.app.logging_config import configure_logging
from api.app.membership import DEMO_TENANT_ID
from api.app.settings import Settings, get_settings
from api.app.tenant import clear_client_id, get_client_id, set_client_id
from worker.queues import QUEUE_DEFAULT, QUEUE_LOW


def build_beat_schedule(settings: Settings) -> dict[str, Any]:
    """
    Beat entries from Settings (Sprint 29.3).

    Import-time wiring still calls ``get_settings()`` once; tests / future
    reload can rebuild via this factory without copying the table.
    """
    return {
        "demo-tenant-heartbeat": {
            "task": "worker.heartbeat",
            "schedule": 60.0,
            "kwargs": {
                "message": "beat",
                "tenant_id": str(DEMO_TENANT_ID),
                "priority": 0,
            },
            "options": {
                "queue": QUEUE_DEFAULT,
                "headers": {"client_id": str(DEMO_TENANT_ID)},
            },
        },
        "slack-history-sync-hourly": {
            "task": "worker.dispatch_slack_history_syncs",
            "schedule": float(settings.slack_history_sync_interval_seconds),
            "options": {
                "queue": QUEUE_LOW,
            },
        },
        "recurring-report-daily": {
            "task": "worker.dispatch_recurring_reports",
            "schedule": float(settings.recurring_report_daily_interval_seconds),
            "kwargs": {"cadence": "daily"},
            "options": {
                "queue": QUEUE_DEFAULT,
            },
        },
        "recurring-report-weekly": {
            "task": "worker.dispatch_recurring_reports",
            "schedule": float(settings.recurring_report_weekly_interval_seconds),
            "kwargs": {"cadence": "weekly"},
            "options": {
                "queue": QUEUE_DEFAULT,
            },
        },
    }


configure_logging()
settings = get_settings()

celery_app = Celery(
    "client_slack_agents",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_default_queue=QUEUE_DEFAULT,
    worker_prefetch_multiplier=1,
    # Sprint 5 exit: Beat fires demo-tenant heartbeat; worker logs client_id.
    # Sprint 9.4: hourly dispatcher enqueues sync for enabled tenants with install.
    beat_schedule=build_beat_schedule(settings),
)


@before_task_publish.connect
def _inject_client_id_header(headers: dict | None = None, **_kwargs) -> None:
    if headers is None:
        return
    client_id = get_client_id()
    if client_id and "client_id" not in headers:
        headers["client_id"] = client_id


@task_prerun.connect
def _restore_client_id(task=None, **_kwargs) -> None:
    headers = getattr(getattr(task, "request", None), "headers", None) or {}
    set_client_id(headers.get("client_id"))


@task_postrun.connect
def _clear_client_id(**_kwargs) -> None:
    clear_client_id()


# Ensure tasks register when the app module is imported (worker / beat / API).
celery_app.loader.import_default_modules()
