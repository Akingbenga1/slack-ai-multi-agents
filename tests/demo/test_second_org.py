"""Second-org stand-up + knowledge isolation (Sprint 22.4 / PO-04)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.admin.provision import (
    OrganisationError,
    create_organisation,
    ensure_organisation,
)
from api.app.db.models import (
    AgentConfig,
    AuditLog,
    BillingCustomer,
    Membership,
    Role,
    Tenant,
    User,
)
from api.app.demo.isolation import prove_no_knowledge_leak
from api.app.membership import DEMO_TENANT_ID
from api.app.settings import Settings
from tests.retrieval.helpers import memory_client, memory_settings


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


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret="test-secret-at-least-32-chars-long!")


def test_create_organisation_wires_admin_billing_agent(db: Session, settings: Settings):
    created = create_organisation(
        db,
        name="Acme Co",
        slug="acme-co",
        admin_email="acme@example.com",
        admin_password="acmeadmin1",
        activate_plan=True,
        actor_email="owner@example.com",
        settings=settings,
    )
    assert created.created is True
    assert created.tenant.slug == "acme-co"
    assert created.admin.email == "acme@example.com"

    billing = db.scalar(
        select(BillingCustomer).where(BillingCustomer.tenant_id == created.tenant.id)
    )
    assert billing is not None
    assert billing.plan_status == "active"
    assert billing.entitlements.get("agent") is True

    agent = db.scalar(
        select(AgentConfig).where(AgentConfig.tenant_id == created.tenant.id)
    )
    assert agent is not None

    audits = list(db.scalars(select(AuditLog)).all())
    assert any(a.action == "tenant.created" for a in audits)


def test_create_organisation_rejects_duplicate_slug(db: Session, settings: Settings):
    create_organisation(
        db,
        name="One",
        slug="dup-org",
        admin_email="one@example.com",
        admin_password="password1",
        settings=settings,
    )
    with pytest.raises(OrganisationError, match="slug already exists"):
        create_organisation(
            db,
            name="Two",
            slug="dup-org",
            admin_email="two@example.com",
            admin_password="password1",
            settings=settings,
        )


def test_ensure_organisation_is_idempotent(db: Session, settings: Settings):
    first = ensure_organisation(
        db,
        name="Second Organisation",
        slug="second-org",
        admin_email="admin-second@example.com",
        admin_password="second123",
        activate_plan=True,
        settings=settings,
    )
    second = ensure_organisation(
        db,
        name="Second Organisation",
        slug="second-org",
        admin_email="admin-second@example.com",
        admin_password="second123",
        activate_plan=True,
        settings=settings,
    )
    assert first.created is True
    assert second.created is False
    assert first.tenant.id == second.tenant.id


def test_second_org_knowledge_does_not_leak():
    settings = memory_settings()
    client = memory_client()
    tenant_a = str(DEMO_TENANT_ID)
    tenant_b = str(uuid4())
    result = prove_no_knowledge_leak(
        tenant_a=tenant_a,
        tenant_b=tenant_b,
        settings=settings,
        client=client,
    )
    assert result["no_leak"] is True
    assert result["mode"] == "injected"
