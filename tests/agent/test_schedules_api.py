"""API smoke for unified /agent/schedules (Task 28.3 / 28.4)."""

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
    monkeypatch.setattr("api.app.agent.routes.read_all_kinds", schedules.read_all_kinds)
    monkeypatch.setattr("api.app.agent.routes.patch_schedules", schedules.patch_schedules)

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


def test_get_and_patch_agent_schedules(client: TestClient):
    headers = {
        "Authorization": f"Bearer {_token()}",
        "X-Client-Id": str(DEMO_TENANT_ID),
    }
    get_res = client.get("/agent/schedules", headers=headers)
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["schedules"]["slack_history_sync"]["enabled"] is True
    assert body["schedules"]["recurring_report"]["enabled"] is False

    patch_res = client.patch(
        "/agent/schedules",
        headers=headers,
        json={
            "slack_history_sync": {"enabled": False},
            "recurring_report": {
                "enabled": True,
                "channel_id": "C_AGENT",
                "cadence": "daily",
            },
        },
    )
    assert patch_res.status_code == 200
    out = patch_res.json()["schedules"]
    assert out["slack_history_sync"]["enabled"] is False
    assert out["recurring_report"]["enabled"] is True
    assert out["recurring_report"]["channel_id"] == "C_AGENT"
    assert out["recurring_report"]["cadence"] == "daily"
