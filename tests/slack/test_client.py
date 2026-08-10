"""Unit tests for Slack Web API client (Task 9.1)."""

from __future__ import annotations

from typing import Any, Callable

import httpx
import pytest

from api.app.slack.client import (
    SlackApiError,
    SlackRateLimitError,
    SlackWebClient,
)

_RealClient = httpx.Client


def _json_response(
    payload: dict[str, Any],
    *,
    status_code: int = 200,
    headers: dict | None = None,
) -> httpx.Response:
    return httpx.Response(status_code, json=payload, headers=headers or {})


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    transport = httpx.MockTransport(handler)

    def factory(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs = {**kwargs, "transport": transport}
        return _RealClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)


def test_conversations_list_paginates(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        cursor = request.url.params.get("cursor")
        if not cursor:
            return _json_response(
                {
                    "ok": True,
                    "channels": [{"id": "C1", "name": "general"}],
                    "response_metadata": {"next_cursor": "page2"},
                }
            )
        assert cursor == "page2"
        return _json_response(
            {
                "ok": True,
                "channels": [{"id": "C2", "name": "ops"}],
                "response_metadata": {"next_cursor": ""},
            }
        )

    _patch_client(monkeypatch, handler)
    client = SlackWebClient("xoxb-test", sleep=lambda _: None)
    channels = list(client.conversations_list())
    assert [c["id"] for c in channels] == ["C1", "C2"]
    assert len(calls) == 2


def test_conversations_history_oldest_and_pages(monkeypatch: pytest.MonkeyPatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/conversations.history")
        params = request.url.params
        assert params["channel"] == "C111"
        assert params["oldest"] == "100.0"
        cursor = params.get("cursor")
        if not cursor:
            return _json_response(
                {
                    "ok": True,
                    "messages": [{"ts": "101.0", "text": "a", "user": "U1"}],
                    "response_metadata": {"next_cursor": "h2"},
                }
            )
        return _json_response(
            {
                "ok": True,
                "messages": [{"ts": "102.0", "text": "b", "user": "U2"}],
                "response_metadata": {"next_cursor": ""},
            }
        )

    _patch_client(monkeypatch, handler)
    client = SlackWebClient("xoxb-test", sleep=lambda _: None)
    messages = list(client.conversations_history("C111", oldest="100.0"))
    assert [m["ts"] for m in messages] == ["101.0", "102.0"]


def test_rate_limit_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return _json_response(
                {"ok": False, "error": "ratelimited"},
                status_code=429,
                headers={"Retry-After": "2"},
            )
        return _json_response({"ok": True, "channels": [{"id": "C9"}], "response_metadata": {}})

    _patch_client(monkeypatch, handler)
    client = SlackWebClient("xoxb-test", max_retries=3, sleep=sleeps.append)
    channels = list(client.conversations_list())
    assert [c["id"] for c in channels] == ["C9"]
    assert sleeps == [2.0]
    assert attempts["n"] == 2


def test_rate_limit_exhausted(monkeypatch: pytest.MonkeyPatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {"ok": False, "error": "ratelimited"},
            status_code=429,
            headers={"Retry-After": "1"},
        )

    _patch_client(monkeypatch, handler)
    client = SlackWebClient("xoxb-test", max_retries=1, sleep=lambda _: None)
    with pytest.raises(SlackRateLimitError) as exc:
        list(client.conversations_list())
    assert exc.value.retry_after == 1.0


def test_http_503_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(503, text="unavailable")
        return _json_response(
            {"ok": True, "channels": [{"id": "C503"}], "response_metadata": {}}
        )

    _patch_client(monkeypatch, handler)
    client = SlackWebClient("xoxb-test", max_retries=2, sleep=sleeps.append)
    channels = list(client.conversations_list())
    assert [c["id"] for c in channels] == ["C503"]
    assert attempts["n"] == 2
    assert len(sleeps) == 1


def test_api_error_not_ok(monkeypatch: pytest.MonkeyPatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"ok": False, "error": "missing_scope"})

    _patch_client(monkeypatch, handler)
    client = SlackWebClient("xoxb-test", sleep=lambda _: None)
    with pytest.raises(SlackApiError) as exc:
        list(client.conversations_list())
    assert exc.value.error == "missing_scope"
