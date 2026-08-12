"""Public org self-signup (Sprint 31.1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.admin.provision import OrganisationError, create_organisation
from api.app.auth.signup import register_organisation
from api.app.auth.tokens import decode_access_token
from api.app.db.models import (
    AgentConfig,
    AuditLog,
    BillingCustomer,
    Membership,
    Role,
    Tenant,
    User,
)
from api.app.db.session import get_db
from api.app.main import app
from api.app.settings import Settings, get_settings


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        demo_activate_plan=True,
    )


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        Role.__table__,
        Tenant.__table__,
        User.__table__,
        Membership.__table__,
        AgentConfig.__table__,
        BillingCustomer.__table__,
        AuditLog.__table__,
    ):
        table.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_register_organisation_wires_rows_without_plan(db: Session, settings: Settings):
    result = register_organisation(
        db,
        name="Acme Co",
        email="rep@acme.example",
        password="password1",
        settings=settings,
    )
    org = result.organisation
    assert org.created is True
    assert org.tenant.slug == "acme-co"
    assert org.admin.email == "rep@acme.example"

    billing = db.scalar(
        select(BillingCustomer).where(BillingCustomer.tenant_id == org.tenant.id)
    )
    assert billing is not None
    assert billing.plan_status == "inactive"

    agent = db.scalar(select(AgentConfig).where(AgentConfig.tenant_id == org.tenant.id))
    assert agent is not None

    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == org.admin.id,
            Membership.tenant_id == org.tenant.id,
        )
    )
    assert membership is not None

    audits = list(db.scalars(select(AuditLog)).all())
    assert any(
        a.action == "tenant.created" and (a.detail or {}).get("source") == "self_signup"
        for a in audits
    )

    principal = decode_access_token(result.access_token, settings)
    assert principal.role == "org_admin"
    assert principal.tenant_id == str(org.tenant.id)
    assert principal.email == "rep@acme.example"


def test_register_rejects_duplicate_email(db: Session, settings: Settings):
    register_organisation(
        db,
        name="One",
        email="dup@example.com",
        password="password1",
        slug="one-org",
        settings=settings,
    )
    with pytest.raises(OrganisationError, match="already exists"):
        register_organisation(
            db,
            name="Two",
            email="dup@example.com",
            password="password1",
            slug="two-org",
            settings=settings,
        )


def test_two_signups_are_isolated_tenants(db: Session, settings: Settings):
    a = register_organisation(
        db,
        name="Alpha",
        email="a@alpha.example",
        password="password1",
        settings=settings,
    )
    b = register_organisation(
        db,
        name="Beta",
        email="b@beta.example",
        password="password1",
        settings=settings,
    )
    assert a.organisation.tenant.id != b.organisation.tenant.id
    assert a.organisation.admin.id != b.organisation.admin.id
    assert decode_access_token(a.access_token, settings).tenant_id != decode_access_token(
        b.access_token, settings
    ).tenant_id


def test_signup_http_creates_org_and_token(db: Session, settings: Settings):
    def _override_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as client:
            res = client.post(
                "/auth/signup",
                json={
                    "name": "New Co",
                    "email": "newco-rep@example.com",
                    "password": "password1",
                },
            )
            assert res.status_code == 201, res.text
            body = res.json()
            assert body["role"] == "org_admin"
            assert body["all_access"] is False
            assert body["tenant"]["name"] == "New Co"
            assert body["admin"]["email"] == "newco-rep@example.com"
            assert body["access_token"]

            login = client.post(
                "/auth/token",
                json={"email": "newco-rep@example.com", "password": "password1"},
            )
            assert login.status_code == 200
            assert login.json()["tenant_id"] == body["tenant_id"]

            me = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {body['access_token']}"},
            )
            assert me.status_code == 200
            assert me.json()["tenant_id"] == body["tenant_id"]
    finally:
        app.dependency_overrides.clear()


def test_signup_http_duplicate_email_conflict(db: Session, settings: Settings):
    create_organisation(
        db,
        name="Existing",
        slug="existing",
        admin_email="taken@example.com",
        admin_password="password1",
        settings=settings,
    )

    def _override_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as client:
            res = client.post(
                "/auth/signup",
                json={
                    "name": "Other Co",
                    "email": "taken@example.com",
                    "password": "password1",
                    "slug": "other-co",
                },
            )
            assert res.status_code == 409
    finally:
        app.dependency_overrides.clear()
