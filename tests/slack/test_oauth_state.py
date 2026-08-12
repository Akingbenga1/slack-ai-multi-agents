"""Slack OAuth signed state (security hardening)."""

from __future__ import annotations

from uuid import uuid4

import jwt
import pytest

from api.app.auth.tokens import create_access_token, decode_access_token
from api.app.settings import Settings
from api.app.slack.oauth_state import create_slack_oauth_state, verify_slack_oauth_state


def test_create_and_verify_oauth_state():
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    tid = str(uuid4())
    token = create_slack_oauth_state(settings=settings, tenant_id=tid, actor_sub="user-1")
    out_tid, out_sub = verify_slack_oauth_state(token, settings)
    assert out_tid == tid
    assert out_sub == "user-1"


def test_reject_tampered_state():
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    token = create_slack_oauth_state(
        settings=settings, tenant_id=str(uuid4()), actor_sub="user-1"
    )
    with pytest.raises(ValueError, match="invalid_oauth_state"):
        verify_slack_oauth_state(token + "x", settings)


def test_all_access_not_elevated_from_jwt_claim():
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    token = create_access_token(
        settings=settings,
        sub="u1",
        email="a@example.com",
        role="org_admin",
        tenant_id=str(uuid4()),
    )
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    payload["all_access"] = True
    forged = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    principal = decode_access_token(forged, settings)
    assert principal.role == "org_admin"
    assert principal.all_access is False
