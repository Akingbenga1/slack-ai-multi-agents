"""API tests for /tools/cli-host check and install control plane."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.auth.tokens import create_access_token
from api.app.db.models import Tenant, ToolRegistry
from api.app.db.session import get_db
from api.app.db.tool_store import insert_tool_registry
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
        cli_host_install_enabled=True,
    )


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Tenant.__table__.create(engine)
    ToolRegistry.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        tid = DEMO_TENANT_ID
        session.add(Tenant(id=tid, slug="demo", name="Demo", status="active"))
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


def _token(settings: Settings) -> str:
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=str(DEMO_TENANT_ID),
    )


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token(settings)}",
        "X-Client-Id": str(DEMO_TENANT_ID),
    }


def test_list_cli_host_tools(client: TestClient, db: Session, settings: Settings):
    insert_tool_registry(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="jq",
        kind="cli",
        description="JSON processor",
        config={"command": "jq", "install": ["brew", "install", "jq"]},
    )
    insert_tool_registry(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="search_knowledge",
        kind="code",
        description="internal",
        config={},
    )
    db.commit()

    res = client.get("/cli-host", headers=_headers(settings))
    assert res.status_code == 200
    body = res.json()
    assert body["install_enabled"] is True
    assert len(body["tools"]) == 1
    assert body["tools"][0]["name"] == "jq"
    assert body["tools"][0]["command"] == "jq"
    assert body["tools"][0]["has_install_spec"] is True


def test_check_cli_host_tool(client: TestClient, db: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch):
    insert_tool_registry(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="jq",
        kind="cli",
        config={"command": "jq"},
    )
    db.commit()
    monkeypatch.setattr("api.app.agent.cli_host.shutil.which", lambda c: f"/bin/{c}")

    res = client.post("/cli-host/jq/check", headers=_headers(settings))
    assert res.status_code == 200
    body = res.json()
    assert body["installed"] is True
    assert body["command"] == "jq"
    assert body["resolved_path"] == "/bin/jq"


def test_install_disabled(client: TestClient, db: Session, settings: Settings):
    settings.cli_host_install_enabled = False
    insert_tool_registry(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="jq",
        kind="cli",
        config={"command": "jq", "install": ["brew", "install", "jq"]},
    )
    db.commit()
    res = client.post("/cli-host/jq/install", headers=_headers(settings))
    assert res.status_code == 403


def test_check_rejects_non_cli(client: TestClient, db: Session, settings: Settings):
    insert_tool_registry(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="http-ping",
        kind="http",
        config={"url": "https://example.com"},
    )
    db.commit()
    res = client.post("/cli-host/http-ping/check", headers=_headers(settings))
    assert res.status_code == 400


def test_update_install_spec(client: TestClient, db: Session, settings: Settings):
    insert_tool_registry(
        db,
        tenant_id=str(DEMO_TENANT_ID),
        name="pngcheck",
        kind="cli",
        description="PNG checker",
        config={"command": "pngcheck"},
    )
    db.commit()

    res = client.patch(
        "/cli-host/pngcheck/install-spec",
        headers=_headers(settings),
        json={
            "package": "pngcheck",
            "install": "winget install -e --id SomeVendor.pngcheck --accept-package-agreements",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "pngcheck"
    assert body["has_install_spec"] is True
    assert body["package"] == "pngcheck"
    assert "winget" in (body.get("install") or "")

    from api.app.db.tool_store import get_tool_registry

    stored = get_tool_registry(db, tenant_id=str(DEMO_TENANT_ID), name="pngcheck")
    assert stored is not None
    assert stored.config["command"] == "pngcheck"
    assert stored.config["package"] == "pngcheck"
    assert "winget" in stored.config["install"]

    clear = client.patch(
        "/cli-host/pngcheck/install-spec",
        headers=_headers(settings),
        json={"package": "", "install": ""},
    )
    assert clear.status_code == 200
    assert clear.json()["has_install_spec"] is False
    stored2 = get_tool_registry(db, tenant_id=str(DEMO_TENANT_ID), name="pngcheck")
    assert stored2 is not None
    assert "package" not in (stored2.config or {})
    assert "install" not in (stored2.config or {})
    assert stored2.config["command"] == "pngcheck"
