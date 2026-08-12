"""IdentityProvider factory + credentials adapter smoke (Sprint 36)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.auth.credentials_adapter import CredentialsIdentityProvider
from api.app.auth.provider import get_identity_provider
from api.app.db.models import Membership, Role, Tenant, User
from api.app.membership import hash_password
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
    for table in (Role, Tenant, User, Membership):
        table.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_factory_defaults_to_credentials():
    provider = get_identity_provider(Settings(identity_provider="credentials"))
    assert isinstance(provider, CredentialsIdentityProvider)
    assert provider.name == "credentials"


def test_factory_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown IDENTITY_PROVIDER"):
        get_identity_provider(Settings(identity_provider="ldap"))


@pytest.mark.parametrize("name", ["oidc", "saml", "google", "microsoft"])
def test_factory_future_idps_not_implemented(name: str):
    with pytest.raises(ValueError, match="not implemented"):
        get_identity_provider(Settings(identity_provider=name))


def test_credentials_verify_success_and_failure(db: Session):
    role = Role(id=uuid4(), name="org_admin", description="org")
    tid = uuid4()
    db.add(role)
    db.add(Tenant(id=tid, slug="acme", name="Acme", status="active"))
    user = User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password=hash_password("admin123"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(Membership(tenant_id=tid, user_id=user.id, role_id=role.id))
    db.commit()

    idp = CredentialsIdentityProvider()
    ok = idp.verify(db, email="admin@example.com", password="admin123")
    assert ok is not None
    assert ok.email == "admin@example.com"
    assert ok.role == "org_admin"
    assert ok.tenant_id == str(tid)
    assert ok.all_access is False

    bad = idp.verify(db, email="admin@example.com", password="wrong")
    assert bad is None
