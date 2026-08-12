"""Unit tests for per-tenant gateway rate limits (Task 12.1)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app.governance.rate_limit import (
    check_tenant_rate_limit,
    is_rate_limit_exempt,
    rate_limit_headers,
)
from api.app.main import app
from api.app.settings import Settings, get_settings


class _FakePipeline:
    def __init__(self, store: dict[str, int]) -> None:
        self._store = store
        self._ops: list[tuple[str, str]] = []

    def incr(self, key: str) -> _FakePipeline:
        self._ops.append(("incr", key))
        return self

    def expire(self, key: str, _seconds: int) -> _FakePipeline:
        self._ops.append(("expire", key))
        return self

    def execute(self) -> list[Any]:
        results: list[Any] = []
        for op, key in self._ops:
            if op == "incr":
                self._store[key] = self._store.get(key, 0) + 1
                results.append(self._store[key])
            else:
                results.append(True)
        self._ops.clear()
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self.store)

    def close(self) -> None:
        return None


def test_is_rate_limit_exempt():
    assert is_rate_limit_exempt("/health") is True
    assert is_rate_limit_exempt("/billing/webhooks/stripe") is True
    assert is_rate_limit_exempt("/docs") is True
    assert is_rate_limit_exempt("/debug/tenant") is False
    assert is_rate_limit_exempt("/jobs/heartbeat") is False


def test_check_allows_under_limit():
    fake = FakeRedis()
    settings = Settings(rate_limit_enabled=True, rate_limit_rpm=5, redis_url="redis://unused")
    cid = str(uuid4())
    for i in range(5):
        d = check_tenant_rate_limit(cid, settings=settings, redis_client=fake, now=1_700_000_000.0)
        assert d.allowed is True
        assert d.remaining == 5 - (i + 1)
        assert d.skipped is False


def test_check_blocks_over_limit():
    fake = FakeRedis()
    settings = Settings(rate_limit_enabled=True, rate_limit_rpm=3, redis_url="redis://unused")
    cid = str(uuid4())
    for _ in range(3):
        assert check_tenant_rate_limit(
            cid, settings=settings, redis_client=fake, now=1_700_000_000.0
        ).allowed
    blocked = check_tenant_rate_limit(
        cid, settings=settings, redis_client=fake, now=1_700_000_000.0
    )
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after >= 1
    headers = rate_limit_headers(blocked)
    assert headers["Retry-After"] == str(blocked.retry_after)
    assert headers["X-RateLimit-Limit"] == "3"


def test_tenants_isolated():
    fake = FakeRedis()
    settings = Settings(rate_limit_enabled=True, rate_limit_rpm=2, redis_url="redis://unused")
    a, b = str(uuid4()), str(uuid4())
    assert check_tenant_rate_limit(a, settings=settings, redis_client=fake).allowed
    assert check_tenant_rate_limit(a, settings=settings, redis_client=fake).allowed
    assert check_tenant_rate_limit(a, settings=settings, redis_client=fake).allowed is False
    assert check_tenant_rate_limit(b, settings=settings, redis_client=fake).allowed is True


def test_disabled_skips():
    fake = FakeRedis()
    settings = Settings(rate_limit_enabled=False, rate_limit_rpm=1, redis_url="redis://unused")
    cid = str(uuid4())
    for _ in range(5):
        d = check_tenant_rate_limit(cid, settings=settings, redis_client=fake)
        assert d.allowed is True
        assert d.skipped is True


def test_empty_client_id_skips():
    fake = FakeRedis()
    settings = Settings(rate_limit_enabled=True, rate_limit_rpm=1, redis_url="redis://unused")
    d = check_tenant_rate_limit("", settings=settings, redis_client=fake)
    assert d.allowed is True
    assert d.skipped is True


def test_redis_error_fails_open():
    class BoomRedis:
        def pipeline(self):
            raise ConnectionError("down")

        def close(self):
            return None

    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_rpm=1,
        rate_limit_fail_open=True,
        redis_url="redis://unused",
    )
    d = check_tenant_rate_limit(str(uuid4()), settings=settings, redis_client=BoomRedis())  # type: ignore[arg-type]
    assert d.allowed is True
    assert d.skipped is True


def test_redis_error_fails_closed_when_configured():
    class BoomRedis:
        def pipeline(self):
            raise ConnectionError("down")

        def close(self):
            return None

    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_rpm=1,
        rate_limit_fail_open=False,
        redis_url="redis://unused",
    )
    d = check_tenant_rate_limit(
        str(uuid4()),
        settings=settings,
        redis_client=BoomRedis(),  # type: ignore[arg-type]
        now=1_700_000_000.0,
    )
    assert d.allowed is False
    assert d.skipped is False


def test_middleware_returns_429(monkeypatch: pytest.MonkeyPatch):
    fake = FakeRedis()
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_rpm=2,
        redis_url="redis://unused",
        jwt_secret="test-secret-at-least-32-chars-long!",
        debug_endpoints_enabled=True,
    )

    monkeypatch.setattr("api.app.middleware.get_settings", lambda: settings)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(
        "api.app.middleware.check_tenant_rate_limit",
        lambda client_id, settings=None: check_tenant_rate_limit(
            client_id, settings=settings or Settings(), redis_client=fake
        ),
    )

    client = TestClient(app)
    cid = str(uuid4())
    headers = {
        "Authorization": f"Bearer {_debug_bearer_token()}",
        "X-Client-Id": cid,
    }
    try:
        assert client.get("/debug/tenant", headers=headers).status_code == 200
        assert client.get("/debug/tenant", headers=headers).status_code == 200
        r = client.get("/debug/tenant", headers=headers)
        assert r.status_code == 429
        assert r.json()["detail"] == "rate_limit_exceeded"
        assert "Retry-After" in r.headers
    finally:
        app.dependency_overrides.clear()


def _debug_bearer_token() -> str:
    from api.app.auth.tokens import create_access_token

    return create_access_token(
        settings=Settings(jwt_secret="test-secret-at-least-32-chars-long!"),
        sub="debug-user",
        email="debug@example.com",
        role="org_admin",
        tenant_id=str(uuid4()),
    )


def test_middleware_skips_without_client_id(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_rpm=1,
        redis_url="redis://unused",
        jwt_secret="test-secret-at-least-32-chars-long!",
        debug_endpoints_enabled=True,
    )
    monkeypatch.setattr("api.app.middleware.get_settings", lambda: settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_debug_bearer_token()}"}
    try:
        # Bearer without X-Client-Id → not rate limited (even if RPM=1)
        for _ in range(3):
            assert client.get("/debug/tenant", headers=headers).status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_health_exempt(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(rate_limit_enabled=True, rate_limit_rpm=1, redis_url="redis://unused")
    monkeypatch.setattr("api.app.middleware.get_settings", lambda: settings)
    monkeypatch.setattr("api.app.auth.deps.get_settings", lambda: settings)
    client = TestClient(app)
    headers = {"X-Client-Id": str(uuid4())}
    # Health is exempt even with client id; may be degraded if deps down
    r = client.get("/health", headers=headers)
    assert r.status_code == 200
