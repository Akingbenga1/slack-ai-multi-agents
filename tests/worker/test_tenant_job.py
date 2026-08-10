"""Sprint 29.2–29.4 worker Template Method smoke + regression tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from api.app.settings import Settings
from worker.celery_app import build_beat_schedule
from worker.job_meta import KIND_HEARTBEAT, STATUS_SUCCEEDED
from worker import tasks as worker_tasks
from worker import tenant_job as tenant_job_mod

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_beat_schedule_uses_settings_intervals():
    settings = Settings(
        slack_history_sync_interval_seconds=12,
        recurring_report_daily_interval_seconds=34,
        recurring_report_weekly_interval_seconds=56,
    )
    schedule = build_beat_schedule(settings)
    assert schedule["slack-history-sync-hourly"]["schedule"] == 12.0
    assert schedule["recurring-report-daily"]["schedule"] == 34.0
    assert schedule["recurring-report-weekly"]["schedule"] == 56.0
    assert schedule["recurring-report-daily"]["kwargs"]["cadence"] == "daily"
    assert schedule["demo-tenant-heartbeat"]["task"] == "worker.heartbeat"


def test_heartbeat_uses_tenant_job_shell(monkeypatch: pytest.MonkeyPatch):
    tenant_id = uuid4()
    job = type(
        "Job",
        (),
        {"id": uuid4(), "status": "pending", "error": None, "result": None},
    )()
    usage_events: list[dict] = []

    class FakeDB:
        def close(self):
            return None

    monkeypatch.setattr(tenant_job_mod, "session_scope", lambda: FakeDB())
    monkeypatch.setattr(
        tenant_job_mod,
        "resolve_tenant_id",
        lambda _tid=None: tenant_id,
    )
    monkeypatch.setattr(tenant_job_mod, "create_job", lambda *_a, **_k: job)
    monkeypatch.setattr(tenant_job_mod, "mark_running", lambda *_a, **_k: job)

    def fake_succeeded(_db, _job, result=None):
        job.status = STATUS_SUCCEEDED
        job.result = result
        return job

    monkeypatch.setattr(tenant_job_mod, "mark_succeeded", fake_succeeded)

    def fake_usage(_db, _tid, event_type, *, units=1, meta=None, commit=True):
        usage_events.append({"event_type": event_type, "meta": meta or {}})

    monkeypatch.setattr(tenant_job_mod, "record_usage", fake_usage)

    result = worker_tasks.heartbeat.run(
        message="ping",
        tenant_id=str(tenant_id),
    )
    assert result["message"] == "ping"
    assert result["client_id"] == str(tenant_id)
    assert result["job_id"] == str(job.id)
    assert job.status == STATUS_SUCCEEDED
    assert usage_events and usage_events[0]["event_type"] == "job"
    assert usage_events[0]["meta"]["kind"] == KIND_HEARTBEAT


def test_tasks_module_has_no_duplicated_job_lifecycle():
    """Exit criteria: domain tasks must not copy session/job/usage boilerplate."""
    source = (_REPO_ROOT / "worker" / "tasks.py").read_text(encoding="utf-8")
    forbidden = (
        "create_job(",
        "mark_running(",
        "mark_succeeded(",
        "mark_failed(",
        "session_scope(",
        "SessionLocal(",
        "record_usage(",
    )
    for needle in forbidden:
        assert needle not in source, f"lifecycle leak in worker/tasks.py: {needle}"
    assert "@tenant_job(" in source
    assert "run_dispatch(" in source
    assert source.count("@tenant_job(") >= 4
    assert source.count("run_dispatch(") >= 2


def test_ingest_pipelines_delegate_to_shared_chunks_core():
    """Exit criteria: embed/upsert lives in ingest_chunks only."""
    slack = (_REPO_ROOT / "api" / "app" / "ingest" / "pipeline.py").read_text(
        encoding="utf-8"
    )
    docs = (
        _REPO_ROOT / "api" / "app" / "ingest" / "document_pipeline.py"
    ).read_text(encoding="utf-8")
    core = (
        _REPO_ROOT / "api" / "app" / "ingest" / "chunks_ingest.py"
    ).read_text(encoding="utf-8")
    assert "ingest_chunks(" in slack
    assert "ingest_chunks(" in docs
    assert "upsert_vectors(" in core
    assert "upsert_vectors(" not in slack
    assert "upsert_vectors(" not in docs
