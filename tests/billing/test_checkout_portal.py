"""Checkout + Portal session unit tests (Tasks 11.2–11.3)."""

from __future__ import annotations

from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.billing.checkout import create_checkout_session
from api.app.billing.customers import BillingError
from api.app.billing.portal import create_portal_session
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


def test_checkout_requires_secret(db: Session):
    tenant = _tenant(db)
    settings = Settings(stripe_secret_key="", stripe_price_id="price_x")
    with pytest.raises(BillingError, match="STRIPE_SECRET_KEY"):
        create_checkout_session(db, tenant_id=tenant.id, email="a@b.co", settings=settings)


def test_checkout_requires_price(db: Session):
    tenant = _tenant(db)
    settings = Settings(stripe_secret_key="sk_test_x", stripe_price_id="")
    with pytest.raises(BillingError, match="STRIPE_PRICE_ID"):
        create_checkout_session(db, tenant_id=tenant.id, email="a@b.co", settings=settings)


def test_checkout_session_url(db: Session, monkeypatch: pytest.MonkeyPatch):
    tenant = _tenant(db)
    settings = Settings(
        stripe_secret_key="sk_test_x",
        stripe_price_id="price_abc",
        web_app_url="http://localhost:3000",
    )
    monkeypatch.setattr(
        "stripe.Customer.create",
        MagicMock(return_value=MagicMock(id="cus_1")),
    )
    session_mock = MagicMock(return_value=MagicMock(url="https://checkout.stripe.com/c/test"))
    monkeypatch.setattr("stripe.checkout.Session.create", session_mock)

    url = create_checkout_session(
        db, tenant_id=tenant.id, email="admin@example.com", settings=settings
    )
    assert url == "https://checkout.stripe.com/c/test"
    kwargs = session_mock.call_args.kwargs
    assert kwargs["mode"] == "subscription"
    assert kwargs["customer"] == "cus_1"
    assert kwargs["line_items"] == [{"price": "price_abc", "quantity": 1}]
    assert "checkout=success" in kwargs["success_url"]
    assert "checkout=cancel" in kwargs["cancel_url"]


def test_portal_session_url(db: Session, monkeypatch: pytest.MonkeyPatch):
    tenant = _tenant(db)
    db.add(
        BillingCustomer(
            tenant_id=tenant.id,
            stripe_customer_id="cus_existing",
            plan_status="inactive",
        )
    )
    db.flush()
    settings = Settings(stripe_secret_key="sk_test_x", web_app_url="http://localhost:3000")
    portal_mock = MagicMock(return_value=MagicMock(url="https://billing.stripe.com/p/test"))
    monkeypatch.setattr("stripe.billing_portal.Session.create", portal_mock)

    url = create_portal_session(
        db, tenant_id=tenant.id, email="admin@example.com", settings=settings
    )
    assert url == "https://billing.stripe.com/p/test"
    kwargs = portal_mock.call_args.kwargs
    assert kwargs["customer"] == "cus_existing"
    assert kwargs["return_url"] == "http://localhost:3000/app/billing"
