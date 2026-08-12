"""Plan / entitlement helpers (Task 11.5)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.billing.plans import (
    ACTIVE_ENTITLEMENTS,
    apply_plan_state,
    plan_is_active,
    tenant_has_entitlement,
)
from api.app.db.models import BillingCustomer, Tenant


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


def test_apply_plan_state_sets_entitlements(db: Session):
    t = Tenant(id=uuid4(), slug="org-e", name="E", status="active")
    db.add(t)
    db.flush()
    row = BillingCustomer(
        tenant_id=t.id,
        external_customer_id="cus_e",
        plan_status="inactive",
        entitlements={"agent": False, "ingest": False, "sync": False},
    )
    db.add(row)
    db.flush()

    apply_plan_state(db, row, plan_status="active", external_subscription_id="sub_e")
    assert row.entitlements == ACTIVE_ENTITLEMENTS
    assert plan_is_active(db, t.id) is True
    assert tenant_has_entitlement(db, t.id, "agent") is True

    apply_plan_state(db, row, plan_status="inactive", clear_subscription=True)
    assert row.entitlements["agent"] is False
    assert plan_is_active(db, t.id) is False
    assert tenant_has_entitlement(db, t.id, "agent") is False
