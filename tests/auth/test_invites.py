"""Tokenised org-admin invites (Sprint 31.3)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.auth.invites import InviteError, accept_invite, create_invite
from api.app.auth.signup import register_organisation
from api.app.db.models import (
    AgentConfig,
    AuditLog,
    BillingCustomer,
    Invite,
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
        web_app_url="http://localhost:3000",
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
        Invite.__table__,
    ):
        table.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_accept_joins_existing_tenant_not_a_new_org(db: Session, settings: Settings):
    signup = register_organisation(
        db,
        name="Acme Co",
        email="owner-admin@example.com",
        password="password1",
        slug="acme-co",
        settings=settings,
    )
    tenant_id = signup.organisation.tenant.id
    created = create_invite(
        db,
        tenant_id=tenant_id,
        email="teammate@example.com",
        actor_user_id=signup.organisation.admin.id,
        actor_email=signup.organisation.admin.email,
        settings=settings,
    )
    assert created.invite_url.startswith("http://localhost:3000/invite?token=")

    accepted = accept_invite(
        db,
        token=created.raw_token,
        password="teammate1",
        settings=settings,
    )
    assert accepted.tenant.id == tenant_id
    assert accepted.user.email == "teammate@example.com"
    tenants = list(db.scalars(select(Tenant)).all())
    assert len(tenants) == 1

    with pytest.raises(InviteError, match="already used"):
        accept_invite(
            db,
            token=created.raw_token,
            password="teammate1",
            settings=settings,
        )


def test_expired_invite_rejected(db: Session, settings: Settings):
    signup = register_organisation(
        db,
        name="Acme Co",
        email="owner-admin@example.com",
        password="password1",
        settings=settings,
    )
    created = create_invite(
        db,
        tenant_id=signup.organisation.tenant.id,
        email="late@example.com",
        actor_user_id=signup.organisation.admin.id,
        actor_email=signup.organisation.admin.email,
        settings=settings,
        ttl=timedelta(seconds=-1),
    )
    with pytest.raises(InviteError, match="expired"):
        accept_invite(
            db,
            token=created.raw_token,
            password="password1",
            settings=settings,
        )


def test_invite_http_create_preview_accept(db: Session, settings: Settings):
    signup = register_organisation(
        db,
        name="Acme Co",
        email="owner-admin@example.com",
        password="password1",
        slug="acme-co",
        settings=settings,
    )

    def _override_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as client:
            created = client.post(
                "/auth/invites",
                headers={
                    "Authorization": f"Bearer {signup.access_token}",
                    "X-Client-Id": str(signup.organisation.tenant.id),
                },
                json={"email": "teammate@example.com"},
            )
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["email"] == "teammate@example.com"
            assert "/invite?token=" in body["invite_url"]
            token = body["token"]

            preview = client.get("/auth/invites/preview", params={"token": token})
            assert preview.status_code == 200
            assert preview.json()["tenant_slug"] == "acme-co"
            assert preview.json()["email"] == "teammate@example.com"

            accepted = client.post(
                "/auth/invites/accept",
                json={"token": token, "password": "teammate1"},
            )
            assert accepted.status_code == 201, accepted.text
            assert accepted.json()["tenant_id"] == str(signup.organisation.tenant.id)
            assert accepted.json()["admin"]["email"] == "teammate@example.com"

            login = client.post(
                "/auth/token",
                json={"email": "teammate@example.com", "password": "teammate1"},
            )
            assert login.status_code == 200
            assert login.json()["tenant_id"] == str(signup.organisation.tenant.id)
    finally:
        app.dependency_overrides.clear()


def test_invite_http_rejects_existing_email(db: Session, settings: Settings):
    signup = register_organisation(
        db,
        name="Acme Co",
        email="owner-admin@example.com",
        password="password1",
        settings=settings,
    )

    def _override_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as client:
            res = client.post(
                "/auth/invites",
                headers={
                    "Authorization": f"Bearer {signup.access_token}",
                    "X-Client-Id": str(signup.organisation.tenant.id),
                },
                json={"email": "owner-admin@example.com"},
            )
            assert res.status_code == 409
    finally:
        app.dependency_overrides.clear()
