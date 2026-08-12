"""API tests for recurring report schedule (Task 17.2 / 28.4)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings
from tests.schedules.helpers import MemorySchedules


@pytest.fixture
def schedules() -> MemorySchedules:
    return MemorySchedules()


@pytest.fixture
def client(schedules: MemorySchedules, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    monkeypatch.setattr(
        "api.app.jobs.routes.get_recurring_report_schedule",
        schedules.get_recurring_report_schedule,
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.set_recurring_report_schedule",
        schedules.set_recurring_report_schedule,
    )

    def _fake_db():
        yield object()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token() -> str:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=str(DEMO_TENANT_ID),
    )


def test_schedule_requires_auth(client: TestClient):
    res = client.get("/jobs/recurring-report/schedule")
    assert res.status_code == 401


def test_schedule_get_defaults(client: TestClient):
    res = client.get(
        "/jobs/recurring-report/schedule",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "recurring_report"
    assert body["enabled"] is False
    assert body["cadence"] == "weekly"
    assert body["channel_id"] is None
    assert body["window_label"] == "last 7 days"


def test_schedule_patch_channel_cadence_enable(
    client: TestClient, schedules: MemorySchedules
):
    headers = {"Authorization": f"Bearer {_token()}"}
    res = client.patch(
        "/jobs/recurring-report/schedule",
        headers=headers,
        json={
            "enabled": True,
            "channel_id": "C_REPORT",
            "cadence": "daily",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is True
    assert body["channel_id"] == "C_REPORT"
    assert body["cadence"] == "daily"
    assert body["window_label"] == "last 24 hours"
    assert (
        schedules.get_recurring_report_schedule(None, DEMO_TENANT_ID)["channel_id"]
        == "C_REPORT"
    )

    res = client.patch(
        "/jobs/recurring-report/schedule",
        headers=headers,
        json={"clear_channel": True, "cadence": "weekly"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["channel_id"] is None
    assert body["cadence"] == "weekly"
    assert body["window_label"] == "last 7 days"


def test_schedule_rejects_bad_cadence(client: TestClient):
    res = client.patch(
        "/jobs/recurring-report/schedule",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"cadence": "hourly"},
    )
    assert res.status_code == 400


def test_force_enqueue(
    client: TestClient, schedules: MemorySchedules, monkeypatch: pytest.MonkeyPatch
):
    from api.app.job_queue import EnqueueResult

    class _FakeQueue:
        name = "celery"

        def enqueue(self, *, kind: str, tenant_id: str, payload=None):
            return EnqueueResult(task_id="report-task-1", queue="default", kind=kind)

    monkeypatch.setattr(
        "api.app.jobs.routes.get_job_queue",
        lambda: _FakeQueue(),
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.require_budget",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.require_entitlement",
        lambda *_a, **_k: None,
    )
    schedules.set_recurring_report_schedule(
        None,
        tenant_id=DEMO_TENANT_ID,
        enabled=True,
        channel_id="C_FORCE",
        cadence="weekly",
    )
    res = client.post(
        "/jobs/recurring-report",
        headers={"Authorization": f"Bearer {_token()}"},
        json={},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["task_id"] == "report-task-1"
    assert body["kind"] == "recurring_report"
    assert body["client_id"] == str(DEMO_TENANT_ID)


def test_force_enqueue_requires_channel(client: TestClient):
    res = client.post(
        "/jobs/recurring-report",
        headers={"Authorization": f"Bearer {_token()}"},
        json={},
    )
    assert res.status_code == 400
