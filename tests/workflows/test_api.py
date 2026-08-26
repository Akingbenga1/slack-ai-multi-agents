"""Workflow library HTTP API tenant isolation (Sprint 24.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.auth.tokens import create_access_token
from api.app.db.models import Tenant, WorkflowTemplate
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID
from api.app.settings import Settings, get_settings
from api.app.workflows.library import store_workflow_template


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@pytest.fixture
def db(tmp_path: Path) -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Tenant.__table__.create(engine)
    WorkflowTemplate.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session, tmp_path: Path):
    def _override_db():
        try:
            yield db
        finally:
            pass

    def _settings():
        return Settings(
            jwt_secret="test-secret-at-least-32-chars-long!",
            upload_dir=str(tmp_path),
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


def test_list_and_copy_isolated(client: TestClient, db: Session, tmp_path: Path):
    a = Tenant(id=uuid4(), slug="a", name="A", status="active")
    b = Tenant(id=uuid4(), slug="b", name="B", status="active")
    db.add_all([a, b])
    db.commit()

    stored = store_workflow_template(
        db,
        client_id=str(a.id),
        upload_root=tmp_path,
        filename="w.csv",
        data=b"k,v\n1,2\n",
        title="A only",
        enqueue_ingest=False,
    )
    db.commit()

    headers_a = {
        "Authorization": f"Bearer {_token(str(a.id))}",
        "X-Client-Id": str(a.id),
    }
    headers_b = {
        "Authorization": f"Bearer {_token(str(b.id))}",
        "X-Client-Id": str(b.id),
    }

    res_a = client.get("/workflows", headers=headers_a)
    assert res_a.status_code == 200
    assert len(res_a.json()["templates"]) == 1

    res_b = client.get("/workflows", headers=headers_b)
    assert res_b.status_code == 200
    assert res_b.json()["templates"] == []

    res_get_b = client.get(f"/workflows/{stored.template.id}", headers=headers_b)
    assert res_get_b.status_code == 404

    res_copy = client.post(
        f"/workflows/{stored.template.id}/copy",
        headers=headers_a,
        json={"owner_slack_user_id": "U_A", "title": "My A draft"},
    )
    assert res_copy.status_code == 200
    body = res_copy.json()
    assert body["visibility"] == "personal"
    assert body["parent_id"] == str(stored.template.id)
    assert body["title"] == "My A draft"


def test_upload_workflow_template(client: TestClient, db: Session, tmp_path: Path):
    tenant = Tenant(id=uuid4(), slug="up", name="Upload Org", status="active")
    db.add(tenant)
    db.commit()

    headers = {
        "Authorization": f"Bearer {_token(str(tenant.id))}",
        "X-Client-Id": str(tenant.id),
    }
    res = client.post(
        "/workflows/upload",
        headers=headers,
        files={"file": ("user-workflow.md", b"# Steps\n1. Read file\n", "text/markdown")},
        data={"title": "User workflow"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["created"] is True
    assert body["ingested_queued"] is False
    assert body["ingest_task_id"] is None
    assert body["title"] == "User workflow"
    assert body["visibility"] == "shared"
    assert body["original_filename"] == "user-workflow.md"
    assert "Read file" in (body["body_text_preview"] or "")

    res_list = client.get("/workflows", headers=headers)
    assert len(res_list.json()["templates"]) == 1


def test_upload_workflow_idempotent(client: TestClient, db: Session, tmp_path: Path):
    tenant = Tenant(id=uuid4(), slug="idem", name="Idem Org", status="active")
    db.add(tenant)
    db.commit()
    headers = {
        "Authorization": f"Bearer {_token(str(tenant.id))}",
        "X-Client-Id": str(tenant.id),
    }
    payload = b"same bytes"
    first = client.post(
        "/workflows/upload",
        headers=headers,
        files={"file": ("flow.md", payload, "text/markdown")},
    )
    second = client.post(
        "/workflows/upload",
        headers=headers,
        files={"file": ("flow-copy.md", payload, "text/markdown")},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["created"] is True
    assert second.json()["created"] is False


def test_upload_workflow_rejects_bad_extension(client: TestClient, db: Session):
    tenant = Tenant(id=uuid4(), slug="bad", name="Bad Org", status="active")
    db.add(tenant)
    db.commit()
    headers = {
        "Authorization": f"Bearer {_token(str(tenant.id))}",
        "X-Client-Id": str(tenant.id),
    }
    res = client.post(
        "/workflows/upload",
        headers=headers,
        files={"file": ("virus.exe", b"bad", "application/octet-stream")},
    )
    assert res.status_code == 400
    assert "not allowed" in res.json()["detail"].lower()


def test_upload_workflow_tenant_isolated(client: TestClient, db: Session):
    a = Tenant(id=uuid4(), slug="ua", name="A", status="active")
    b = Tenant(id=uuid4(), slug="ub", name="B", status="active")
    db.add_all([a, b])
    db.commit()
    headers_a = {
        "Authorization": f"Bearer {_token(str(a.id))}",
        "X-Client-Id": str(a.id),
    }
    headers_b = {
        "Authorization": f"Bearer {_token(str(b.id))}",
        "X-Client-Id": str(b.id),
    }
    res = client.post(
        "/workflows/upload",
        headers=headers_a,
        files={"file": ("only-a.md", b"tenant a", "text/markdown")},
    )
    assert res.status_code == 201
    assert client.get("/workflows", headers=headers_b).json()["templates"] == []
