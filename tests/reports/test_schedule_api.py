"""API tests for recurring report schedule (Task 17.2)."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


class _ReportScheduleStore:
    def __init__(self):
        self.by_tenant: dict[UUID, dict] = {}

    def get(self, _db, tenant_id: UUID) -> dict:
        return dict(
            self.by_tenant.get(
                tenant_id,
                {
                    "enabled": False,
                    "channel_id": None,
                    "cadence": "weekly",
                    "window_label": "last 7 days",
                },
            )
        )

    def set(
        self,
        _db,
        *,
        tenant_id: UUID,
        enabled: bool | None = None,
        channel_id: str | None = None,
        cadence: str | None = None,
        window_label: str | None = None,
        clear_channel: bool = False,
    ):
        cur = self.get(_db, tenant_id)
        if enabled is not None:
            cur["enabled"] = bool(enabled)
        if clear_channel:
            cur["channel_id"] = None
        elif channel_id is not None:
            cur["channel_id"] = channel_id.strip() or None
        if cadence is not None:
            cur["cadence"] = cadence
            if window_label is None:
                cur["window_label"] = (
                    "last 24 hours" if cadence == "daily" else "last 7 days"
                )
        if window_label is not None:
            cur["window_label"] = window_label
        self.by_tenant[tenant_id] = cur
        return object()


@pytest.fixture
def store() -> _ReportScheduleStore:
    return _ReportScheduleStore()


@pytest.fixture
def client(store: _ReportScheduleStore, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    monkeypatch.setattr(
        "api.app.jobs.routes.get_recurring_report_schedule",
        store.get,
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.set_recurring_report_schedule",
        store.set,
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
    client: TestClient, store: _ReportScheduleStore
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
    assert store.by_tenant[DEMO_TENANT_ID]["channel_id"] == "C_REPORT"

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
    client: TestClient, store: _ReportScheduleStore, monkeypatch: pytest.MonkeyPatch
):
    class _FakeAsync:
        id = "report-task-1"

    monkeypatch.setattr(
        "api.app.jobs.routes.enqueue_recurring_report",
        lambda **_kwargs: _FakeAsync(),
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.require_budget",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.require_entitlement",
        lambda *_a, **_k: None,
    )
    store.set(
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
