"""Platform owner role resolution from DB memberships."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.models import Membership, Role, Tenant, User
from api.app.membership import hash_password, resolve_login_principal


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
    for table in (Role, Tenant, User, Membership):
        table.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_roles(db: Session) -> dict[str, Role]:
    rows = {}
    for name in ("platform_owner", "org_admin"):
        row = Role(id=uuid4(), name=name, description=name)
        db.add(row)
        db.flush()
        rows[name] = row
    return rows


def test_platform_owner_requires_db_membership(db: Session):
    roles = _seed_roles(db)
    platform_tid = uuid4()
    db.add(
        Tenant(
            id=platform_tid,
            slug="__platform__",
            name="Platform",
            status="active",
        )
    )
    owner = User(
        id=uuid4(),
        email="owner@example.com",
        hashed_password=hash_password("owner123"),
        is_active=True,
    )
    db.add(owner)
    db.flush()
    db.add(
        Membership(
            tenant_id=platform_tid,
            user_id=owner.id,
            role_id=roles["platform_owner"].id,
        )
    )
    db.commit()

    principal = resolve_login_principal(db, email="owner@example.com", password="owner123")
    assert principal is not None
    assert principal.role == "platform_owner"
    assert principal.all_access is True
    assert principal.tenant_id is None


def test_email_alone_does_not_grant_platform_owner(db: Session):
    roles = _seed_roles(db)
    org_tid = uuid4()
    db.add(Tenant(id=org_tid, slug="demo-org", name="Demo", status="active"))
    impostor = User(
        id=uuid4(),
        email="owner@example.com",
        hashed_password=hash_password("secret"),
        is_active=True,
    )
    db.add(impostor)
    db.flush()
    db.add(
        Membership(
            tenant_id=org_tid,
            user_id=impostor.id,
            role_id=roles["org_admin"].id,
        )
    )
    db.commit()

    principal = resolve_login_principal(db, email="owner@example.com", password="secret")
    assert principal is not None
    assert principal.role == "org_admin"
    assert principal.all_access is False
