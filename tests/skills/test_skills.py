"""Skills catalog + store + API (tenant markdown skills)."""

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
from api.app.blob_store import LocalDiskBlobStore
from api.app.db.models import Tenant
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID
from api.app.settings import Settings, get_settings
from api.app.skills.catalog import catalog_index
from api.app.skills.provider import BlobSkillProvider, build_tenant_skill_runtime
from api.app.skills.store import SkillsStore


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


def test_store_create_updates_catalog_atomically(tmp_path: Path):
    cid = str(uuid4())
    blob = LocalDiskBlobStore(Settings(upload_dir=str(tmp_path)), root=tmp_path)
    store = SkillsStore(client_id=cid, blob_store=blob)
    store.create_folder(name="Finance")
    record = store.create_skill(
        name="Invoice pack",
        description="Build an invoice packet",
        body="# Steps\n\n1. Collect PDFs\n",
        folder_path="Finance",
    )
    assert record.path == "Finance/invoice-pack.md"
    catalog = store.get_catalog()
    index = catalog_index(catalog)
    assert len(index) == 1
    assert index[0]["name"] == "Invoice pack"
    assert index[0]["path"] == "Finance/invoice-pack.md"
    loaded = store.read_skill(record.path)
    assert "Build an invoice packet" in loaded.content
    assert "# Steps" in loaded.content


def test_store_delete_skill_and_folder_updates_catalog(tmp_path: Path):
    cid = str(uuid4())
    blob = LocalDiskBlobStore(root=tmp_path)
    store = SkillsStore(client_id=cid, blob_store=blob)
    store.create_folder(name="Ops")
    store.create_skill(name="Daily report", folder_path="Ops", body="# Go\n")
    store.delete_skill("Ops/daily-report.md")
    assert store.list_index() == []
    store.create_skill(name="Weekly", folder_path="Ops", body="# Week\n")
    store.delete_folder("Ops")
    assert store.get_catalog()["children"] == []
    with pytest.raises(Exception):
        store.read_skill("Ops/weekly.md")


def test_store_relocate_folder_moves_children(tmp_path: Path):
    cid = str(uuid4())
    blob = LocalDiskBlobStore(root=tmp_path)
    store = SkillsStore(client_id=cid, blob_store=blob)
    store.create_folder(name="Inbox")
    store.create_skill(name="Triage", folder_path="Inbox", body="# Triage\n")
    store.delete_folder("Inbox", mode="relocate")
    catalog = store.get_catalog()
    assert all(n.get("name") != "Inbox" for n in catalog["children"])
    assert any(
        n.get("type") == "skill" and n.get("path") == "triage.md"
        for n in catalog["children"]
    )
    loaded = store.read_skill("triage.md")
    assert "# Triage" in loaded.content
    with pytest.raises(Exception):
        store.read_skill("Inbox/triage.md")


def test_progressive_disclosure_index_then_load(tmp_path: Path):
    cid = str(uuid4())
    blob = LocalDiskBlobStore(root=tmp_path)
    store = SkillsStore(client_id=cid, blob_store=blob)
    store.create_skill(
        name="Rename pack",
        description="Rename files in a pack",
        body="Do the rename carefully.\n",
    )
    provider = BlobSkillProvider(store)
    index = provider.list_index()
    assert index[0]["description"] == "Rename files in a pack"
    assert "Do the rename" not in index[0]["description"]
    body = provider.load_markdown(index[0]["path"])
    assert "Do the rename carefully" in body


def test_skill_runtime_tools(tmp_path: Path):
    cid = str(uuid4())
    blob = LocalDiskBlobStore(root=tmp_path)
    store = SkillsStore(client_id=cid, blob_store=blob)
    store.create_skill(name="Alpha", description="First skill", body="# A\n")
    runtime = build_tenant_skill_runtime(
        client_id=cid,
        run_key="r1",
        provider=BlobSkillProvider(store),
    )
    assert len(runtime.tools) == 2
    listed = runtime.tools[0].invoke({})
    assert "Alpha" in listed
    assert "First skill" in listed
    loaded = runtime.tools[1].invoke({"path": "alpha.md"})
    assert "# A" in loaded


def test_api_create_list_delete_isolated(client: TestClient, db: Session):
    a = Tenant(id=uuid4(), slug="sa", name="A", status="active")
    b = Tenant(id=uuid4(), slug="sb", name="B", status="active")
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

    created = client.post(
        "/skills",
        headers=headers_a,
        json={
            "name": "Tenant A skill",
            "description": "Only A",
            "body": "# Hello\n",
        },
    )
    assert created.status_code == 201, created.text
    path = created.json()["path"]

    catalog_a = client.get("/skills/catalog", headers=headers_a)
    assert catalog_a.status_code == 200
    assert len(catalog_a.json()["catalog"]["children"]) == 1

    catalog_b = client.get("/skills/catalog", headers=headers_b)
    assert catalog_b.status_code == 200
    assert catalog_b.json()["catalog"]["children"] == []

    stolen = client.get(f"/skills/file?path={path}", headers=headers_b)
    assert stolen.status_code == 404

    deleted = client.delete(f"/skills/file?path={path}", headers=headers_a)
    assert deleted.status_code == 200
    assert deleted.json()["catalog"]["children"] == []


def test_api_folder_and_skill_tree(client: TestClient, db: Session):
    tenant = Tenant(id=uuid4(), slug="sf", name="F", status="active")
    db.add(tenant)
    db.commit()
    headers = {
        "Authorization": f"Bearer {_token(str(tenant.id))}",
        "X-Client-Id": str(tenant.id),
    }
    folder = client.post(
        "/skills/folders",
        headers=headers,
        json={"name": "Reports", "parent_path": ""},
    )
    assert folder.status_code == 201, folder.text
    skill = client.post(
        "/skills",
        headers=headers,
        json={
            "name": "Monthly",
            "description": "Monthly report skill",
            "body": "# Monthly\n",
            "folder_path": "Reports",
        },
    )
    assert skill.status_code == 201, skill.text
    assert skill.json()["path"] == "Reports/monthly.md"
    index = client.get("/skills/index", headers=headers)
    assert index.status_code == 200
    skills = index.json()["skills"]
    assert len(skills) == 1
    assert skills[0]["path"] == "Reports/monthly.md"
