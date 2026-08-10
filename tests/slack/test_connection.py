"""Slack connection status + OAuth portal redirect (Task 20.3)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.auth.tokens import create_access_token
from api.app.db.models import SlackInstall, Tenant
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Tenant.__table__.create(engine)
    SlackInstall.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session):
    def _override_db():
        yield db

    def _settings():
        return Settings(
            jwt_secret="test-secret-at-least-32-chars-long!",
            public_base_url="https://api.example.test",
            web_app_url="http://localhost:3000",
            slack_client_id="cid",
        )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = _settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(tenant_id: str) -> str:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=tenant_id,
    )


def test_connection_disconnected(client: TestClient, db: Session):
    tid = uuid4()
    db.add(Tenant(id=tid, slug=f"s-{tid.hex[:8]}", name="S", status="active"))
    db.commit()
    res = client.get(
        "/slack/connection",
        headers={"Authorization": f"Bearer {_token(str(tid))}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["connected"] is False
    assert body["client_id"] == str(tid)
    assert f"tenant_id={tid}" in body["install_url"]


def test_connection_connected(client: TestClient, db: Session):
    tid = uuid4()
    db.add(Tenant(id=tid, slug=f"s-{tid.hex[:8]}", name="S", status="active"))
    db.add(
        SlackInstall(
            tenant_id=tid,
            team_id="T123",
            team_name="Acme",
            bot_token_encrypted="x",
            scopes="chat:write",
        )
    )
    db.commit()
    res = client.get(
        "/slack/connection",
        headers={"Authorization": f"Bearer {_token(str(tid))}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["connected"] is True
    assert body["team_id"] == "T123"
    assert body["team_name"] == "Acme"


def test_connection_cross_tenant_denied(client: TestClient):
    res = client.get(
        "/slack/connection",
        headers={
            "Authorization": f"Bearer {_token(str(DEMO_TENANT_ID))}",
            "X-Client-Id": str(uuid4()),
        },
    )
    assert res.status_code == 403


def test_oauth_callback_error_redirects_to_portal(client: TestClient):
    res = client.get(
        "/slack/oauth/callback?error=access_denied",
        follow_redirects=False,
    )
    assert res.status_code in (302, 303, 307)
    loc = res.headers.get("location") or ""
    assert loc.startswith("http://localhost:3000/app/slack")
    assert "error=" in loc
