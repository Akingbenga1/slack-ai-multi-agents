"""Agent config GET/PATCH API (Task 19.1)."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.app.auth.tokens import create_access_token
from api.app.db.models import AgentConfig
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


class _MemDb:
    """Minimal stand-in: one AgentConfig row in memory via monkeypatched store."""

    def __init__(self) -> None:
        self.config = AgentConfig(
            id=UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            tenant_id=DEMO_TENANT_ID,
            name="default",
            system_prompt=None,
            allowlist=None,
            schedules=None,
            extra={"display_name": "Workspace agent"},
        )

    def get(self, _db, tenant_id: UUID):
        from api.app.agent import config_store as store

        assert tenant_id == DEMO_TENANT_ID
        allow = store.normalize_allowlist(self.config.allowlist) if self.config.allowlist else {
            "channels": []
        }
        return {
            "client_id": str(tenant_id),
            "config_id": str(self.config.id),
            "name": store._display_name(self.config),
            "system_prompt": self.config.system_prompt,
            "allowlist": allow,
            "schedules": {
                "slack_history_sync": {"enabled": True},
                "recurring_report": {
                    "enabled": False,
                    "channel_id": None,
                    "cadence": "weekly",
                    "window_label": "last 7 days",
                },
            },
            "updated_at": None,
        }

    def update(self, _db, tenant_id: UUID, **kwargs):
        from api.app.agent import config_store as store

        assert tenant_id == DEMO_TENANT_ID
        if kwargs.get("name") is not None:
            extra = dict(self.config.extra or {})
            extra["display_name"] = kwargs["name"].strip()
            self.config.extra = extra
        if kwargs.get("clear_system_prompt"):
            self.config.system_prompt = None
        elif kwargs.get("system_prompt") is not None:
            text = kwargs["system_prompt"].strip()
            self.config.system_prompt = text or None
        if kwargs.get("clear_allowlist"):
            self.config.allowlist = {"channels": []}
        elif kwargs.get("allowlist") is not None:
            self.config.allowlist = store.normalize_allowlist(kwargs["allowlist"])
        return self.config


@pytest.fixture
def mem() -> _MemDb:
    return _MemDb()


@pytest.fixture
def client(mem: _MemDb, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    monkeypatch.setattr(
        "api.app.agent.routes.agent_settings_dict",
        mem.get,
    )
    monkeypatch.setattr(
        "api.app.agent.routes.update_agent_settings",
        mem.update,
    )

    def _fake_db():
        yield object()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(tenant_id: str | None = None) -> str:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=tenant_id or str(DEMO_TENANT_ID),
    )


def test_config_requires_auth(client: TestClient):
    assert client.get("/agent/config").status_code == 401


def test_config_get_and_patch(client: TestClient, mem: _MemDb):
    headers = {"Authorization": f"Bearer {_token()}"}
    res = client.get("/agent/config", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Workspace agent"
    assert body["allowlist"]["channels"] == []

    res = client.patch(
        "/agent/config",
        headers=headers,
        json={
            "name": "Acme Bot",
            "system_prompt": "Be concise.",
            "allowlist": {"channels": ["C111", "C222"]},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Acme Bot"
    assert body["system_prompt"] == "Be concise."
    assert body["allowlist"]["channels"] == ["C111", "C222"]
    assert mem.config.extra["display_name"] == "Acme Bot"


def test_config_cross_tenant_denied(client: TestClient):
    other = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    res = client.get(
        "/agent/config",
        headers={
            "Authorization": f"Bearer {_token()}",
            "X-Client-Id": other,
        },
    )
    assert res.status_code == 403
