"""Sprint 31.4 — self-signup must not break owner provision or demo seed."""

from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import pytest
from fastapi.testclient import TestClient

from api.app.auth.signup import register_organisation
from api.app.auth.tokens import create_access_token
from api.app.db.models import (
    AgentConfig,
    AuditLog,
    BillingCustomer,
    Job,
    Membership,
    Role,
    SlackInstall,
    SyncWatermark,
    Tenant,
    User,
)
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_OWNER_ID, DEMO_TENANT_ID, ensure_demo_memberships
from api.app.settings import Settings, get_settings
from mcp_server.tools.onboarding import start_onboarding


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        demo_activate_plan=True,
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
        SlackInstall.__table__,
        Job.__table__,
        SyncWatermark.__table__,
    ):
        table.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _owner_headers(settings: Settings) -> dict[str, str]:
    token = create_access_token(
        settings=settings,
        sub=str(DEMO_OWNER_ID),
        email="owner@example.com",
        role="platform_owner",
        tenant_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


def test_no_signup_specific_settings_keys():
    names = set(Settings.model_fields)
    assert "jwt_secret" in names
    assert "web_app_url" in names
    assert "demo_activate_plan" in names
    assert not any("signup" in n or "register" in n for n in names)


def test_demo_seed_activate_plan_survives_self_signup(
    db: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("api.app.membership.get_settings", lambda: settings)

    signup = register_organisation(
        db,
        name="Acme Co",
        email="rep@acme.example",
        password="password1",
        slug="acme-co",
        settings=settings,
    )
    ensure_demo_memberships(db)

    # Column query — SQLite stores well-known demo UUIDs as floats, so ORM
    # entity load of DEMO_TENANT_ID fails. Slug + plan_status are enough.
    plans = dict(
        db.execute(
            select(Tenant.slug, BillingCustomer.plan_status).join(
                BillingCustomer, BillingCustomer.tenant_id == Tenant.id
            )
        ).all()
    )
    metas = dict(
        db.execute(
            select(Tenant.slug, BillingCustomer.meta).join(
                BillingCustomer, BillingCustomer.tenant_id == Tenant.id
            )
        ).all()
    )
    assert plans["demo-org"] == "active"
    demo_meta = metas["demo-org"] or {}
    if isinstance(demo_meta, str):
        demo_meta = json.loads(demo_meta)
    assert demo_meta.get("source") == "demo_seed"
    assert plans["acme-co"] == "inactive"
    assert signup.organisation.tenant.id != DEMO_TENANT_ID


def test_admin_create_still_works_after_signup(db: Session, settings: Settings):
    signup = register_organisation(
        db,
        name="Acme Co",
        email="rep@acme.example",
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
            denied = client.post(
                "/admin/tenants",
                json={
                    "name": "Gamma Co",
                    "slug": "gamma-co",
                    "admin_email": "gamma@example.com",
                    "admin_password": "gammaadmin1",
                    "activate_plan": True,
                },
            )
            assert denied.status_code == 401

            res = client.post(
                "/admin/tenants",
                headers=_owner_headers(settings),
                json={
                    "name": "Gamma Co",
                    "slug": "gamma-co",
                    "admin_email": "gamma@example.com",
                    "admin_password": "gammaadmin1",
                    "activate_plan": True,
                },
            )
            assert res.status_code == 201, res.text
            body = res.json()
            assert body["tenant"]["slug"] == "gamma-co"
            assert body["tenant"]["plan_status"] == "active"
            assert body["admin"]["email"] == "gamma@example.com"
            assert body["tenant"]["id"] != str(signup.organisation.tenant.id)

            listed = client.get("/admin/tenants", headers=_owner_headers(settings))
            assert listed.status_code == 200
            slugs = {t["slug"] for t in listed.json()["tenants"]}
            assert {"acme-co", "gamma-co"} <= slugs
    finally:
        app.dependency_overrides.clear()

    # Column query avoids ORM UUID load of actor_user_id=DEMO_OWNER_ID on SQLite.
    audit_rows = list(db.execute(select(AuditLog.action, AuditLog.detail)))
    sources = set()
    for action, detail in audit_rows:
        if isinstance(detail, str):
            detail = json.loads(detail)
        sources.add((action, (detail or {}).get("source")))
    assert ("tenant.created", "self_signup") in sources
    assert ("tenant.created", "admin_provision") in sources

    acme_billing = db.scalar(
        select(BillingCustomer).where(
            BillingCustomer.tenant_id == signup.organisation.tenant.id
        )
    )
    assert acme_billing is not None
    assert acme_billing.plan_status == "inactive"


def test_slack_onboarding_stub_is_not_tenant_signup():
    out = start_onboarding(client_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert out["configured"] is False
    assert out["status"] == "not_configured"
    assert "not configured" in out["message"].lower()
