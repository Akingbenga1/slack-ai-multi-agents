"""JWT refresh (portal session continuity)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from api.app.auth.tokens import create_access_token, refresh_access_token
from api.app.settings import Settings


def _settings() -> Settings:
    return Settings(jwt_secret="test-secret-at-least-32-characters-long")


def test_refresh_access_token_mints_new_jwt():
    settings = _settings()
    sub = str(uuid4())
    old = create_access_token(
        settings=settings,
        sub=sub,
        email="owner@example.com",
        role="platform_owner",
        tenant_id=None,
        expires_minutes=60,
    )
    new = refresh_access_token(old, settings)
    payload = jwt.decode(new, settings.jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == sub
    assert payload["email"] == "owner@example.com"
    assert payload["role"] == "platform_owner"
    assert new != old


def test_refresh_access_token_allows_expired_within_grace():
    settings = _settings()
    sub = str(uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": "admin@example.com",
        "role": "org_admin",
        "tenant_id": str(uuid4()),
        "all_access": False,
        "iat": now - timedelta(hours=13),
        "exp": now - timedelta(hours=1),
    }
    expired = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    new = refresh_access_token(expired, settings)
    decoded = jwt.decode(new, settings.jwt_secret, algorithms=["HS256"])
    assert decoded["sub"] == sub


def test_refresh_access_token_rejects_too_old():
    settings = _settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid4()),
        "email": "admin@example.com",
        "role": "org_admin",
        "tenant_id": str(uuid4()),
        "all_access": False,
        "iat": now - timedelta(days=40),
        "exp": now - timedelta(days=31),
    }
    stale = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        refresh_access_token(stale, settings)
    assert exc.value.status_code == 401
    assert "too old" in exc.value.detail.lower()
