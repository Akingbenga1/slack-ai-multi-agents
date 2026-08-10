"""API tests for Slack history sync enqueue + schedule (Task 9.4 / 28.4)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_OWNER_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings
from tests.schedules.helpers import FakeScheduleDB, MemorySchedules


class _FakeAsync:
    id = "sync-task-1"


@pytest.fixture
def schedules() -> MemorySchedules:
    return MemorySchedules()


@pytest.fixture
def client(schedules: MemorySchedules, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    monkeypatch.setattr(
        "api.app.jobs.routes.enqueue_slack_history_sync",
        lambda **_kwargs: _FakeAsync(),
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.is_slack_history_sync_enabled",
        schedules.is_slack_history_sync_enabled,
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.set_slack_history_sync_enabled",
        schedules.set_slack_history_sync_enabled,
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.require_budget",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.require_entitlement",
        lambda *_a, **_k: None,
    )

    def _fake_db():
        yield object()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(*, role: str = "org_admin", tenant_id: str | None = None) -> str:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    if role == "platform_owner":
        return create_access_token(
            settings=settings,
            sub=str(DEMO_OWNER_ID),
            email="owner@example.com",
            role="platform_owner",
            tenant_id=None,
        )
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=tenant_id or str(DEMO_TENANT_ID),
    )


def test_enqueue_requires_auth(client: TestClient):
    res = client.post("/jobs/slack-history-sync", json={})
    assert res.status_code == 401


def test_enqueue_rejects_cross_tenant(client: TestClient):
    other = str(uuid4())
    res = client.post(
        "/jobs/slack-history-sync",
        headers={"Authorization": f"Bearer {_token()}", "X-Client-Id": other},
        json={},
    )
    assert res.status_code == 403


def test_enqueue_returns_task_id(client: TestClient):
    res = client.post(
        "/jobs/slack-history-sync",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"priority": -1},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["task_id"] == "sync-task-1"
    assert body["client_id"] == str(DEMO_TENANT_ID)
    assert body["queue"] == "low"
    assert body["kind"] == "slack_history_sync"


def test_schedule_get_and_patch(client: TestClient, schedules: MemorySchedules):
    headers = {"Authorization": f"Bearer {_token()}"}
    res = client.get("/jobs/slack-history-sync/schedule", headers=headers)
    assert res.status_code == 200
    assert res.json()["enabled"] is True

    res = client.patch(
        "/jobs/slack-history-sync/schedule",
        headers=headers,
        json={"enabled": False},
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is False
    assert schedules.is_slack_history_sync_enabled(None, DEMO_TENANT_ID) is False

    res = client.get("/jobs/slack-history-sync/schedule", headers=headers)
    assert res.json()["enabled"] is False


def test_dispatch_enqueues_due_tenants(monkeypatch: pytest.MonkeyPatch):
    from worker import tasks as worker_tasks

    t1, t2 = uuid4(), uuid4()
    enqueued: list[str] = []

    from worker import tenant_job as tenant_job_mod

    monkeypatch.setattr(tenant_job_mod, "session_scope", lambda: FakeScheduleDB())
    monkeypatch.setattr(
        worker_tasks,
        "list_due_for_kind",
        lambda _db, _key: [t1, t2],
    )

    class _R:
        def __init__(self, tid: str):
            self.id = f"task-{tid[:8]}"

    def fake_enqueue(*, client_id: str, **_kwargs):
        enqueued.append(client_id)
        return _R(client_id)

    monkeypatch.setattr(worker_tasks, "enqueue_slack_history_sync", fake_enqueue)

    result = worker_tasks.dispatch_slack_history_syncs.run()
    assert result["count"] == 2
    assert enqueued == [str(t1), str(t2)]
