"""Retry helper unit tests (Sprint 22.5)."""

from __future__ import annotations

import httpx
import pytest

from api.app.http_retry import call_with_retries, is_transient_http_status
from api.app.tei.client import TeiClient, TeiError


def test_call_with_retries_succeeds_after_transient():
    sleeps: list[float] = []
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return "ok"

    assert call_with_retries(flaky, max_retries=3, sleep=sleeps.append, label="t") == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2


def test_call_with_retries_gives_up():
    def always() -> None:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(httpx.ReadTimeout):
        call_with_retries(always, max_retries=2, sleep=lambda _: None, label="t")


def test_tei_embed_retries_on_503(monkeypatch: pytest.MonkeyPatch):
    from api.app.settings import Settings

    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        embedding_dim=2,
        tei_url="http://tei.test",
    )
    client = TeiClient(settings, max_retries=2)
    attempts = {"n": 0}

    class _Resp:
        def __init__(self, status: int, payload):
            self.status_code = status
            self._payload = payload
            self.text = str(payload)

        def json(self):
            return self._payload

    class _Http:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            attempts["n"] += 1
            if attempts["n"] < 2:
                return _Resp(503, "busy")
            return _Resp(200, [[0.0, 1.0]])

    monkeypatch.setattr("api.app.tei.client.httpx.Client", _Http)
    vecs = client.embed("hello")
    assert vecs == [[0.0, 1.0]]
    assert attempts["n"] == 2


def test_tei_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch):
    from api.app.settings import Settings

    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        embedding_dim=2,
        tei_url="http://tei.test",
    )
    client = TeiClient(settings, max_retries=3)
    attempts = {"n": 0}

    class _Resp:
        status_code = 400
        text = "bad"

        def json(self):
            return {}

    class _Http:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            attempts["n"] += 1
            return _Resp()

    monkeypatch.setattr("api.app.tei.client.httpx.Client", _Http)
    with pytest.raises(TeiError, match="HTTP 400"):
        client.embed("hello")
    assert attempts["n"] == 1


def test_is_transient_http_status():
    assert is_transient_http_status(429)
    assert is_transient_http_status(503)
    assert not is_transient_http_status(400)
