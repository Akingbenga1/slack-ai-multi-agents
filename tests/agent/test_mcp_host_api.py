"""API tests for /mcp-host readiness control plane."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.auth.tokens import create_access_token
from api.app.db.models import McpServer, Tenant, ToolRegistry
from api.app.db.session import get_db
from api.app.db.tool_store import insert_mcp_server, insert_tool_registry
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "CHAR(32)"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        mcp_host_check_timeout_seconds=5.0,
    )


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Tenant.__table__.create(engine)
    McpServer.__table__.create(engine)
    ToolRegistry.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        session.add(
            Tenant(id=DEMO_TENANT_ID, slug="demo", name="Demo", status="active")
        )
        session.commit()
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session, settings: Settings) -> TestClient:
    def _fake_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _headers(settings: Settings) -> dict[str, str]:
    token = create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=str(DEMO_TENANT_ID),
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Client-Id": str(DEMO_TENANT_ID),
    }


def test_list_mcp_host_servers(client: TestClient, db: Session, settings: Settings):
    server = insert_mcp_server(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="docs-mcp",
        transport="http",
        connection_config={"url": "https://example.com/mcp"},
        enabled=True,
    )
    insert_tool_registry(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="search_docs",
        kind="mcp",
        description="docs",
        mcp_server_id=server.id,
        config={},
    )
    db.commit()

    res = client.get("/mcp-host", headers=_headers(settings))
    assert res.status_code == 200
    body = res.json()
    assert body["check_timeout_seconds"] == 5.0
    assert body["bundled"]["id"] == "__bundled__"
    assert len(body["servers"]) == 1
    row = body["servers"][0]
    assert row["name"] == "docs-mcp"
    assert row["endpoint_hint"] == "https://example.com/mcp"
    assert row["linked_tools"] == ["search_docs"]


def test_check_mcp_host_missing_url(client: TestClient, db: Session, settings: Settings):
    insert_mcp_server(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="empty-http",
        transport="http",
        connection_config={},
        enabled=True,
    )
    db.commit()

    res = client.post("/mcp-host/empty-http/check", headers=_headers(settings))
    assert res.status_code == 200
    body = res.json()
    assert body["ready"] is False
    assert "missing URL" in (body["error"] or "")


def test_check_mcp_host_disabled(client: TestClient, db: Session, settings: Settings):
    insert_mcp_server(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="off",
        transport="http",
        connection_config={"url": "https://example.com/mcp"},
        enabled=False,
    )
    db.commit()

    res = client.post("/mcp-host/off/check", headers=_headers(settings))
    assert res.status_code == 200
    body = res.json()
    assert body["ready"] is False
    assert body["enabled"] is False


def test_patch_mcp_host_enabled(client: TestClient, db: Session, settings: Settings):
    insert_mcp_server(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="toggle-me",
        transport="http",
        connection_config={"url": "https://example.com/mcp"},
        enabled=True,
    )
    db.commit()

    res = client.patch(
        "/mcp-host/toggle-me",
        headers=_headers(settings),
        json={"enabled": False},
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is False


def test_check_bundled_mcp(client: TestClient, settings: Settings):
    res = client.post("/mcp-host/bundled/check", headers=_headers(settings))
    assert res.status_code == 200
    body = res.json()
    assert body["server_name"] == "__bundled__"
    assert body["transport"] == "bundled"
    assert body["ready"] is True
