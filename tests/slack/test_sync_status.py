"""Unit tests for Slack sync status (Task 9.5)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings
from api.app.slack import sync_status as status_mod


def _job(*, status: str, result=None, error=None):
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    return type(
        "Job",
        (),
        {
            "id": uuid4(),
            "status": status,
            "finished_at": now,
            "created_at": now,
            "error": error,
            "result": result,
        },
    )()


def test_status_payload(monkeypatch: pytest.MonkeyPatch):
    tenant_id = uuid4()
    success = _job(status="succeeded", result={"message_count": 2})
    failure = _job(status="failed", error="rate limited")

    def fake_latest(_db, *, tenant_id, status=None):
        if status == "succeeded":
            return success
        if status == "failed":
            return failure
        return success

    monkeypatch.setattr(status_mod, "_latest_job", fake_latest)
    monkeypatch.setattr(status_mod, "is_slack_history_sync_enabled", lambda *_a: True)

    class FakeDB:
        def __init__(self):
            self.n = 0

        def scalar(self, _stmt):
            self.n += 1
            if self.n == 1:
                return object()  # SlackInstall
            if self.n == 2:
                return 4  # channel_count
            return datetime(2026, 8, 8, 11, 0, tzinfo=timezone.utc)

    payload = status_mod.get_slack_history_sync_status(FakeDB(), tenant_id)
    assert payload["client_id"] == str(tenant_id)
    assert payload["enabled"] is True
    assert payload["slack_connected"] is True
    assert payload["last_success"]["result"]["message_count"] == 2
    assert payload["last_failure"]["error"] == "rate limited"
    assert payload["watermarks"]["channel_count"] == 4
    assert payload["watermarks"]["last_synced_at"].startswith("2026-08-08")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    monkeypatch.setattr(
        "api.app.jobs.routes.get_slack_history_sync_status",
        lambda _db, tenant_id: {
            "client_id": str(tenant_id),
            "kind": "slack_history_sync",
            "enabled": True,
            "slack_connected": False,
            "last_success": None,
            "last_failure": None,
            "last_job": None,
            "watermarks": {"channel_count": 0, "last_synced_at": None},
        },
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


def test_status_requires_auth(client: TestClient):
    assert client.get("/jobs/slack-history-sync/status").status_code == 401


def test_status_ok(client: TestClient):
    res = client.get(
        "/jobs/slack-history-sync/status",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["client_id"] == str(DEMO_TENANT_ID)
    assert body["kind"] == "slack_history_sync"
    assert body["watermarks"]["channel_count"] == 0
