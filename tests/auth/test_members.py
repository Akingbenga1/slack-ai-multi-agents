"""Org team membership API (list members, remove access, revoke invites)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.auth.invites import accept_invite, create_invite
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


def test_members_list_remove_and_revoke_invite(db: Session, settings: Settings):
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
    accepted = accept_invite(
        db,
        token=created.raw_token,
        password="teammate1",
        settings=settings,
    )
    assert accepted.user.email == "teammate@example.com"

    pending = create_invite(
        db,
        tenant_id=tenant_id,
        email="pending@example.com",
        actor_user_id=signup.organisation.admin.id,
        actor_email=signup.organisation.admin.email,
        settings=settings,
    )

    def _override_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _override_db
    headers = {
        "Authorization": f"Bearer {signup.access_token}",
        "X-Client-Id": str(tenant_id),
    }
    try:
        with TestClient(app) as client:
            listed = client.get("/auth/members", headers=headers)
            assert listed.status_code == 200, listed.text
            members = listed.json()["members"]
            assert len(members) == 2
            emails = {m["email"] for m in members}
            assert emails == {"owner-admin@example.com", "teammate@example.com"}

            self_remove = client.delete(
                f"/auth/members/{signup.organisation.admin.id}",
                headers=headers,
            )
            assert self_remove.status_code == 409

            removed = client.delete(
                f"/auth/members/{accepted.user.id}",
                headers=headers,
            )
            assert removed.status_code == 204, removed.text
            remaining = client.get("/auth/members", headers=headers)
            assert remaining.json()["count"] == 1

            revoked = client.delete(
                f"/auth/invites/{pending.invite.id}",
                headers=headers,
            )
            assert revoked.status_code == 204, revoked.text
            invites = client.get("/auth/invites", headers=headers)
            pending_rows = [
                row for row in invites.json()["invites"] if row["email"] == "pending@example.com"
            ]
            assert pending_rows == []

            audit_actions = {
                row.action
                for row in db.scalars(select(AuditLog)).all()
            }
            assert "member.removed" in audit_actions
            assert "invite.revoked" in audit_actions
    finally:
        app.dependency_overrides.clear()


def test_cannot_remove_last_member(db: Session, settings: Settings):
    signup = register_organisation(
        db,
        name="Solo Co",
        email="solo@example.com",
        password="password1",
        settings=settings,
    )
    tenant_id = signup.organisation.tenant.id
    admin_id = signup.organisation.admin.id

    def _override_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _override_db
    headers = {
        "Authorization": f"Bearer {signup.access_token}",
        "X-Client-Id": str(tenant_id),
    }
    try:
        with TestClient(app) as client:
            res = client.delete(f"/auth/members/{admin_id}", headers=headers)
            assert res.status_code == 409
    finally:
        app.dependency_overrides.clear()
