"""Unit tests for Stripe customer ensure (Task 11.1)."""

from __future__ import annotations

from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.billing.customers import BillingError, ensure_billing_customer, get_billing_customer
from api.app.db.models import BillingCustomer, Tenant
from api.app.settings import Settings


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
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _tenant(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"org-{uuid4().hex[:8]}", name="Test Org", status="active")
    db.add(t)
    db.flush()
    return t


def test_ensure_creates_local_row_without_stripe(db: Session):
    tenant = _tenant(db)
    settings = Settings(stripe_secret_key="")
    row = ensure_billing_customer(db, tenant_id=tenant.id, settings=settings)
    db.commit()
    assert row.tenant_id == tenant.id
    assert row.stripe_customer_id is None
    assert row.plan_status == "inactive"
    assert get_billing_customer(db, tenant.id) is not None


def test_ensure_idempotent_local(db: Session):
    tenant = _tenant(db)
    settings = Settings(stripe_secret_key="")
    a = ensure_billing_customer(db, tenant_id=tenant.id, settings=settings)
    b = ensure_billing_customer(db, tenant_id=tenant.id, settings=settings)
    assert a.id == b.id


def test_ensure_creates_stripe_customer(db: Session, monkeypatch: pytest.MonkeyPatch):
    tenant = _tenant(db)
    settings = Settings(stripe_secret_key="sk_test_fake")

    fake_customer = MagicMock()
    fake_customer.id = "cus_test_123"

    create_mock = MagicMock(return_value=fake_customer)
    monkeypatch.setattr("stripe.Customer.create", create_mock)

    row = ensure_billing_customer(
        db,
        tenant_id=tenant.id,
        email="admin@example.com",
        settings=settings,
    )
    assert row.stripe_customer_id == "cus_test_123"
    create_mock.assert_called_once()
    kwargs = create_mock.call_args.kwargs
    assert kwargs["email"] == "admin@example.com"
    assert kwargs["metadata"]["tenant_id"] == str(tenant.id)
    assert kwargs["metadata"]["client_id"] == str(tenant.id)


def test_ensure_reuses_existing_stripe_id(db: Session, monkeypatch: pytest.MonkeyPatch):
    tenant = _tenant(db)
    db.add(
        BillingCustomer(
            tenant_id=tenant.id,
            stripe_customer_id="cus_existing",
            plan_status="inactive",
        )
    )
    db.flush()
    create_mock = MagicMock()
    monkeypatch.setattr("stripe.Customer.create", create_mock)
    settings = Settings(stripe_secret_key="sk_test_fake")
    row = ensure_billing_customer(db, tenant_id=tenant.id, settings=settings)
    assert row.stripe_customer_id == "cus_existing"
    create_mock.assert_not_called()


def test_ensure_missing_tenant(db: Session):
    settings = Settings(stripe_secret_key="")
    with pytest.raises(BillingError, match="Tenant not found"):
        ensure_billing_customer(db, tenant_id=uuid4(), settings=settings)
