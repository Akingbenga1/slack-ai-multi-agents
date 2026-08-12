"""Sprint 32.4 — plan override entitlements, suspend independence, billing regression."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.admin.actions import override_tenant_plan
from api.app.auth.tokens import create_access_token
from api.app.billing.checkout import create_checkout_session
from api.app.billing.plans import (
    plan_is_active,
    tenant_has_entitlement,
    tenants_with_entitlement,
)
from api.app.db.models import AuditLog, BillingCustomer, Tenant
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_OWNER_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


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
    BillingCustomer.__table__.create(engine)
    AuditLog.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret="test-secret-at-least-32-chars-long!")


def _tenant(db: Session, *, status: str = "active") -> Tenant:
    t = Tenant(
        id=uuid4(),
        slug=f"org-{uuid4().hex[:8]}",
        name="Plan Override Org",
        status=status,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db.add(t)
    db.flush()
    return t


def _billing_row(db: Session, tenant_id) -> BillingCustomer:
    row = db.scalar(select(BillingCustomer).where(BillingCustomer.tenant_id == tenant_id))
    assert row is not None
    return row


def test_plan_override_entitlements_gate(db: Session):
    tenant = _tenant(db)
    db.add(
        BillingCustomer(
            tenant_id=tenant.id,
            plan_status="inactive",
            plan_source="stripe",
            entitlements={"agent": False, "ingest": False, "sync": False},
        )
    )
    db.commit()

    override_tenant_plan(
        db,
        tenant.id,
        plan_status="active",
        reason="trial",
        actor_user_id=None,
        actor_email="owner@example.com",
        settings=Settings(app_env="development"),
    )
    db.commit()

    for flag in ("agent", "ingest", "sync"):
        assert tenant_has_entitlement(db, tenant.id, flag) is True
    assert plan_is_active(db, tenant.id) is True

    override_tenant_plan(
        db,
        tenant.id,
        plan_status="inactive",
        reason="trial ended",
        actor_user_id=None,
        actor_email="owner@example.com",
        settings=Settings(app_env="development"),
    )
    db.commit()

    for flag in ("agent", "ingest", "sync"):
        assert tenant_has_entitlement(db, tenant.id, flag) is False
    assert plan_is_active(db, tenant.id) is False


def test_suspend_blocks_despite_active_plan(db: Session):
    tenant = _tenant(db, status="suspended")
    db.add(
        BillingCustomer(
            tenant_id=tenant.id,
            plan_status="active",
            plan_source="admin",
            override_reason="support",
            entitlements={"agent": True, "ingest": True, "sync": True},
        )
    )
    db.commit()

    assert plan_is_active(db, tenant.id) is False
    assert tenant_has_entitlement(db, tenant.id, "agent") is False
    assert tenants_with_entitlement(db, [tenant.id], "sync") == set()


def test_allow_plan_waivers_guardrail(db: Session):
    tenant = _tenant(db)
    db.add(
        BillingCustomer(
            tenant_id=tenant.id,
            plan_status="inactive",
            plan_source="stripe",
            entitlements={"agent": False},
        )
    )
    db.commit()

    with pytest.raises(PermissionError, match="ALLOW_PLAN_WAIVERS"):
        override_tenant_plan(
            db,
            tenant.id,
            plan_status="active",
            reason="blocked",
            actor_user_id=None,
            actor_email="owner@example.com",
            settings=Settings(app_env="production", allow_plan_waivers=False),
        )

    row = _billing_row(db, tenant.id)
    row.plan_status = "active"
    row.plan_source = "admin"
    db.commit()

    override_tenant_plan(
        db,
        tenant.id,
        plan_status="inactive",
        reason="restore stripe",
        actor_user_id=None,
        actor_email="owner@example.com",
        settings=Settings(app_env="production", allow_plan_waivers=False),
    )
    db.refresh(row)
    assert row.plan_source == "stripe"
    assert row.plan_status == "inactive"


def test_checkout_works_for_stripe_managed_customer(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    """Paying-customer path (OR-02) unchanged when plan is stripe-managed."""
    tenant = _tenant(db)
    db.add(
        BillingCustomer(
            tenant_id=tenant.id,
            external_customer_id="cus_existing",
            plan_status="inactive",
            plan_source="stripe",
            entitlements={"agent": False},
        )
    )
    db.commit()

    settings = Settings(
        stripe_secret_key="sk_test_x",
        stripe_price_id="price_abc",
        web_app_url="http://localhost:3000",
    )
    monkeypatch.setattr(
        "stripe.checkout.Session.create",
        MagicMock(return_value=MagicMock(url="https://checkout.stripe.com/c/pay")),
    )

    url = create_checkout_session(
        db, tenant_id=tenant.id, email="admin@example.com", settings=settings
    )
    assert url.startswith("https://checkout.stripe.com/")


def test_plan_waivers_default_by_app_env():
    assert Settings(app_env="development").plan_waivers_permitted() is True
    assert Settings(app_env="production").plan_waivers_permitted() is False
    assert Settings(app_env="production", allow_plan_waivers=True).plan_waivers_permitted() is True


def test_api_plan_waiver_denied_in_production(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    """HTTP 403 when activating waiver with ALLOW_PLAN_WAIVERS=false."""
    from tests.admin.test_admin_api import _FakeDB

    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-org",
        name="Demo Organisation",
        status="active",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db = _FakeDB([tenant])
    db.billing[tenant.id] = BillingCustomer(
        id=uuid4(),
        tenant_id=tenant.id,
        plan_status="inactive",
        plan_source="stripe",
        entitlements={"agent": False},
        meta={},
    )

    prod = settings.model_copy(update={"app_env": "production", "allow_plan_waivers": False})

    monkeypatch.setattr(
        "api.app.admin.actions.ensure_billing_customer",
        lambda _db, tenant_id, **_kw: db.billing[DEMO_TENANT_ID],
    )

    def _fake_db():
        yield db

    token = create_access_token(
        settings=prod,
        sub=str(DEMO_OWNER_ID),
        email="owner@example.com",
        role="platform_owner",
        tenant_id=None,
    )

    app.dependency_overrides[get_settings] = lambda: prod
    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            res = client.patch(
                f"/admin/tenants/{DEMO_TENANT_ID}/plan",
                headers={"Authorization": f"Bearer {token}"},
                json={"plan_status": "active", "reason": "nope"},
            )
            assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()
