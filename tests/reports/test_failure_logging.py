"""Failure logging for recurring report jobs (Task 17.4)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from worker import tasks as worker_tasks
from worker.job_meta import KIND_RECURRING_REPORT, STATUS_FAILED


def test_recurring_report_failure_marks_job_and_usage(
    monkeypatch: pytest.MonkeyPatch,
):
    tenant_id = uuid4()
    job = type(
        "Job",
        (),
        {"id": uuid4(), "status": "pending", "error": None, "result": None},
    )()
    usage_events: list[dict] = []
    failed: list[str] = []

    class FakeDB:
        def close(self):
            return None

    monkeypatch.setattr(worker_tasks, "session_scope", lambda: FakeDB())
    monkeypatch.setattr(
        worker_tasks,
        "_resolve_tenant_id",
        lambda _tid=None: tenant_id,
    )
    monkeypatch.setattr(
        worker_tasks,
        "create_job",
        lambda *_a, **_k: job,
    )
    monkeypatch.setattr(worker_tasks, "mark_running", lambda *_a, **_k: job)

    def fake_failed(_db, _job, err: str):
        failed.append(err)
        job.status = STATUS_FAILED
        job.error = err
        return job

    monkeypatch.setattr(worker_tasks, "mark_failed", fake_failed)
    monkeypatch.setattr(
        worker_tasks,
        "post_recurring_report",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("slack down")),
    )

    def fake_usage(_db, _tid, event_type, *, units=1, meta=None, commit=True):
        usage_events.append({"event_type": event_type, "meta": meta or {}})

    monkeypatch.setattr(worker_tasks, "record_usage", fake_usage)

    with pytest.raises(RuntimeError, match="slack down"):
        worker_tasks.recurring_report_task.run(
            tenant_id=str(tenant_id),
            channel_id="C1",
            prefer_sync=False,
        )

    assert job.status == STATUS_FAILED
    assert failed and "slack down" in failed[0]
    assert any(
        e["event_type"] == "job"
        and e["meta"].get("kind") == KIND_RECURRING_REPORT
        and e["meta"].get("status") == "failed"
        for e in usage_events
    )
