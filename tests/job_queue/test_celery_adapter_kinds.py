"""CeleryJobQueue kind routing smoke (Sprint 38.3)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.app.job_queue import CeleryJobQueue
from api.app.settings import Settings
from worker.job_meta import (
    KIND_HEARTBEAT,
    KIND_INGEST_UPLOAD,
    KIND_RECURRING_REPORT,
    KIND_SLACK_HISTORY_SYNC,
)


class _FakeAsync:
    def __init__(self, task_id: str):
        self.id = task_id


def test_adapter_routes_all_product_kinds(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, dict]] = []
    tenant = str(uuid4())
    queue = CeleryJobQueue(Settings(job_queue="celery"))
    import worker.tasks as tasks_mod

    def _patch(attr: str, kind_label: str) -> None:
        class _Task:
            @staticmethod
            def apply_async(*, kwargs, **opts):
                calls.append((kind_label, {"kwargs": kwargs, "opts": opts}))
                return _FakeAsync(f"id-{kind_label}")

        # Adapter does `from worker.tasks import …` per enqueue — patch module attrs.
        monkeypatch.setattr(tasks_mod, attr, _Task)

    _patch("heartbeat", KIND_HEARTBEAT)
    _patch("ingest_upload_task", KIND_INGEST_UPLOAD)
    _patch("slack_history_sync_task", KIND_SLACK_HISTORY_SYNC)
    _patch("recurring_report_task", KIND_RECURRING_REPORT)

    r1 = queue.enqueue(
        kind=KIND_HEARTBEAT,
        tenant_id=tenant,
        payload={"message": "ping", "priority": 0},
    )
    assert r1.task_id == f"id-{KIND_HEARTBEAT}"
    assert r1.kind == KIND_HEARTBEAT
    assert r1.queue == "default"

    r2 = queue.enqueue(
        kind=KIND_INGEST_UPLOAD,
        tenant_id=tenant,
        payload={
            "relative_path": f"{tenant}/document/a.csv",
            "filename": "a.csv",
            "file_role": "document",
            "priority": 0,
        },
    )
    assert r2.kind == KIND_INGEST_UPLOAD
    assert r2.task_id == f"id-{KIND_INGEST_UPLOAD}"

    r3 = queue.enqueue(
        kind=KIND_SLACK_HISTORY_SYNC,
        tenant_id=tenant,
        payload={},
    )
    assert r3.kind == KIND_SLACK_HISTORY_SYNC
    assert r3.queue == "low"

    r4 = queue.enqueue(
        kind=KIND_RECURRING_REPORT,
        tenant_id=tenant,
        payload={"channel_id": "C1", "prefer_sync": True},
    )
    assert r4.kind == KIND_RECURRING_REPORT

    kinds = [c[0] for c in calls]
    assert kinds == [
        KIND_HEARTBEAT,
        KIND_INGEST_UPLOAD,
        KIND_SLACK_HISTORY_SYNC,
        KIND_RECURRING_REPORT,
    ]


def test_adapter_ingest_requires_path_fields():
    queue = CeleryJobQueue(Settings(job_queue="celery"))
    with pytest.raises(ValueError, match="ingest_upload requires"):
        queue.enqueue(
            kind=KIND_INGEST_UPLOAD,
            tenant_id=str(uuid4()),
            payload={"filename": "a.csv"},
        )
