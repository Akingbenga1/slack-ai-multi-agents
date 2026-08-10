"""Usage event recording (Task 12.3)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.models import Tenant, UsageEvent
from api.app.governance.usage import (
    EVENT_LLM_TOKENS,
    EVENT_SLACK_MENTION,
    EVENT_SYNC_RUN,
    record_usage,
)


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
    UsageEvent.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_record_usage_persists(db: Session):
    t = Tenant(id=uuid4(), slug="u1", name="U", status="active")
    db.add(t)
    db.commit()

    row = record_usage(
        db,
        t.id,
        EVENT_SLACK_MENTION,
        units=1,
        meta={"channel": "C1"},
        commit=True,
    )
    assert row.id is not None
    assert row.event_type == EVENT_SLACK_MENTION
    assert row.units == 1
    assert row.meta == {"channel": "C1"}

    record_usage(db, t.id, EVENT_SYNC_RUN, units=1, commit=True)
    record_usage(db, t.id, EVENT_LLM_TOKENS, units=42, commit=True)

    rows = list(db.scalars(select(UsageEvent).where(UsageEvent.tenant_id == t.id)))
    assert len(rows) == 3
    token_row = next(r for r in rows if r.event_type == EVENT_LLM_TOKENS)
    assert token_row.units == 42
