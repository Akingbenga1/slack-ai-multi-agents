"""Heartbeat enqueue API via JobQueue (Sprint 38.3)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.db.session import get_db
from api.app.job_queue import EnqueueResult
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


class _FakeQueue:
    name = "celery"
    last: dict | None = None

    def enqueue(self, *, kind: str, tenant_id: str, payload=None):
        self.last = {"kind": kind, "tenant_id": tenant_id, "payload": dict(payload or {})}
        return EnqueueResult(task_id="hb-task-1", queue="default", kind=kind)


@pytest.fixture
def fake_queue() -> _FakeQueue:
    return _FakeQueue()


@pytest.fixture
def client(fake_queue: _FakeQueue, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    monkeypatch.setattr(
        "api.app.jobs.routes.get_job_queue",
        lambda: fake_queue,
    )
    monkeypatch.setattr(
        "api.app.jobs.routes.require_budget",
        lambda *_a, **_k: None,
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


def test_heartbeat_requires_auth(client: TestClient):
    res = client.post("/jobs/heartbeat", json={})
    assert res.status_code == 401


def test_heartbeat_rejects_cross_tenant(client: TestClient):
    other = str(uuid4())
    res = client.post(
        "/jobs/heartbeat",
        headers={"Authorization": f"Bearer {_token()}", "X-Client-Id": other},
        json={},
    )
    assert res.status_code == 403


def test_heartbeat_enqueue_returns_task_id(
    client: TestClient, fake_queue: _FakeQueue
):
    res = client.post(
        "/jobs/heartbeat",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "api-stub", "priority": 0},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["task_id"] == "hb-task-1"
    assert body["client_id"] == str(DEMO_TENANT_ID)
    assert body["queue"] == "default"
    assert body["kind"] == "heartbeat"
    assert fake_queue.last is not None
    assert fake_queue.last["kind"] == "heartbeat"
    assert fake_queue.last["tenant_id"] == str(DEMO_TENANT_ID)
    assert fake_queue.last["payload"]["message"] == "api-stub"
