"""API tests for tenant and admin MCP server install endpoints."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent.mcp_host import McpCheckResult
from api.app.auth.tokens import create_access_token
from api.app.db.models import AuditLog, McpServer, Tenant
from api.app.db.session import get_db
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
    AuditLog.__table__.create(engine)
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


def _org_headers(settings: Settings) -> dict[str, str]:
    token = create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="org@example.com",
        role="org_admin",
        tenant_id=str(DEMO_TENANT_ID),
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Client-Id": str(DEMO_TENANT_ID),
    }


def _owner_headers(settings: Settings) -> dict[str, str]:
    token = create_access_token(
        settings=settings,
        sub=str(uuid4()),
        email="owner@example.com",
        role="platform_owner",
        tenant_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


def _ready_result(*, name: str = "docs") -> McpCheckResult:
    return McpCheckResult(
        server_name=name,
        transport="http",
        ready=True,
        enabled=True,
        endpoint="https://mcp.example.com/mcp",
        tool_count=2,
        tool_names=["search", "fetch"],
        error=None,
        detail="initialize ok · 2 tool(s)",
    )


def test_org_rep_installs_mcp_immediately(
    client: TestClient, db: Session, settings: Settings
):
    with patch(
        "api.app.mcp_servers.service.verify_remote_mcp",
        return_value=_ready_result(name="docs"),
    ):
        res = client.post(
            "/mcp-servers",
            headers=_org_headers(settings),
            json={
                "name": "docs",
                "url": "https://mcp.example.com/mcp",
                "service_token": "tenant-service-secret",
            },
        )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "docs"
    assert body["enabled"] is True
    assert body["has_service_credential"] is True
    assert "service_token" not in body
    assert body["readiness"]["ready"] is True
    assert body["readiness"]["tool_names"] == ["search", "fetch"]

    listed = client.get("/mcp-servers", headers=_org_headers(settings))
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["servers"][0]["has_service_credential"] is True


def test_org_rep_can_install_unavailable_without_token(
    client: TestClient, db: Session, settings: Settings
):
    with patch(
        "api.app.mcp_servers.service.verify_remote_mcp",
        return_value=_ready_result(name="public"),
    ):
        res = client.post(
            "/mcp-servers",
            headers=_org_headers(settings),
            json={
                "name": "public",
                "url": "https://mcp.example.com/public",
                "enabled": False,
                "verify": True,
            },
        )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["enabled"] is False
    assert body["has_service_credential"] is False


def test_admin_lists_and_declines_tenant_mcp(
    client: TestClient, db: Session, settings: Settings
):
    with patch(
        "api.app.mcp_servers.service.verify_remote_mcp",
        return_value=_ready_result(name="docs"),
    ):
        created = client.post(
            "/mcp-servers",
            headers=_org_headers(settings),
            json={
                "name": "docs",
                "url": "https://mcp.example.com/mcp",
                "service_token": "tenant-service-secret",
            },
        )
    server_id = created.json()["id"]

    listed = client.get(
        f"/admin/tenants/{DEMO_TENANT_ID}/mcp-servers",
        headers=_owner_headers(settings),
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    declined = client.post(
        f"/admin/tenants/{DEMO_TENANT_ID}/mcp-servers/{server_id}/decline",
        headers=_owner_headers(settings),
    )
    assert declined.status_code == 200
    assert declined.json()["enabled"] is False

    approved = client.post(
        f"/admin/tenants/{DEMO_TENANT_ID}/mcp-servers/{server_id}/approve",
        headers=_owner_headers(settings),
    )
    assert approved.status_code == 200
    assert approved.json()["enabled"] is True


def test_admin_full_crud(
    client: TestClient, db: Session, settings: Settings
):
    with patch(
        "api.app.mcp_servers.service.verify_remote_mcp",
        return_value=_ready_result(name="ops"),
    ):
        created = client.post(
            f"/admin/tenants/{DEMO_TENANT_ID}/mcp-servers",
            headers=_owner_headers(settings),
            json={
                "name": "ops",
                "url": "https://mcp.example.com/ops",
                "service_token": "admin-installed-secret",
            },
        )
    assert created.status_code == 201, created.text
    server_id = created.json()["id"]

    with patch(
        "api.app.mcp_servers.service.verify_remote_mcp",
        return_value=_ready_result(name="ops-renamed"),
    ):
        updated = client.patch(
            f"/admin/tenants/{DEMO_TENANT_ID}/mcp-servers/{server_id}",
            headers=_owner_headers(settings),
            json={"name": "ops-renamed", "verify": True},
        )
    assert updated.status_code == 200
    assert updated.json()["name"] == "ops-renamed"

    deleted = client.delete(
        f"/admin/tenants/{DEMO_TENANT_ID}/mcp-servers/{server_id}",
        headers=_owner_headers(settings),
    )
    assert deleted.status_code == 204
    assert (
        client.get(
            f"/admin/tenants/{DEMO_TENANT_ID}/mcp-servers/{server_id}",
            headers=_owner_headers(settings),
        ).status_code
        == 404
    )


def test_org_rep_cannot_call_admin_endpoints(
    client: TestClient, settings: Settings
):
    res = client.get(
        f"/admin/tenants/{DEMO_TENANT_ID}/mcp-servers",
        headers=_org_headers(settings),
    )
    assert res.status_code == 403
