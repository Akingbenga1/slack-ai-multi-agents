"""Slack Web API client for live history sync (conversations.list / history)."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from api.app.logging_config import get_logger
from api.app.settings import Settings
from api.app.slack.store import (
    get_bot_token,
    get_install_by_team,
    get_install_by_tenant,
)

logger = get_logger("api.slack.client")

SLACK_API_BASE = "https://slack.com/api"


class SlackApiError(RuntimeError):
    """Slack Web API returned ok=false or an unexpected response."""

    def __init__(self, error: str, *, method: str, response: dict[str, Any] | None = None) -> None:
        self.error = error
        self.method = method
        self.response = response
        super().__init__(f"Slack API {method} failed: {error}")


class SlackRateLimitError(SlackApiError):
    """Rate limit exhausted after retries."""

    def __init__(self, *, method: str, retry_after: float, response: dict[str, Any] | None = None) -> None:
        self.retry_after = retry_after
        super().__init__("ratelimited", method=method, response=response)


class SlackWebClient:
    """Thin httpx client for Slack Web API with pagination and rate-limit retries."""

    def __init__(
        self,
        bot_token: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not bot_token:
            raise ValueError("bot_token is required")
        self.bot_token = bot_token
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleep

    def api_call(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GET https://slack.com/api/{method}; retry on 429 / 5xx / transport errors."""
        return self._request("GET", method, params=params)

    def api_call_post(
        self,
        method: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST https://slack.com/api/{method} (form and/or multipart)."""
        return self._request("POST", method, data=data, files=files)

    def _request(
        self,
        http_method: str,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{SLACK_API_BASE}/{method.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.bot_token}"}
        query: dict[str, str] | None = None
        form: dict[str, str] | None = None
        if http_method.upper() == "GET":
            query = _stringify_params(params)
        else:
            form = _stringify_params(data)

        last_retry_after = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    if http_method.upper() == "GET":
                        resp = client.get(url, headers=headers, params=query)
                    else:
                        resp = client.post(
                            url,
                            headers=headers,
                            data=form,
                            files=files,
                        )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt >= self.max_retries:
                    raise SlackApiError(
                        f"transport_{type(exc).__name__}",
                        method=method,
                        response={"error": str(exc)[:300]},
                    ) from exc
                delay = min(8.0, 0.5 * (2**attempt))
                logger.warning(
                    "slack transport error method=%s attempt=%s retry_in=%.1fs err=%s",
                    method,
                    attempt + 1,
                    delay,
                    exc,
                )
                self._sleep(delay)
                continue

            retry_after = _retry_after_seconds(resp)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_retry_after = (
                    retry_after
                    if resp.status_code == 429
                    else min(8.0, 0.5 * (2**attempt))
                )
                if attempt >= self.max_retries:
                    if resp.status_code == 429:
                        raise SlackRateLimitError(
                            method=method,
                            retry_after=last_retry_after,
                            response=_safe_json(resp),
                        )
                    raise SlackApiError(
                        f"http_{resp.status_code}",
                        method=method,
                        response={"body": resp.text[:300]},
                    )
                logger.warning(
                    "slack http %s method=%s attempt=%s retry_after=%.1fs",
                    resp.status_code,
                    method,
                    attempt + 1,
                    last_retry_after,
                )
                self._sleep(last_retry_after)
                continue

            if resp.status_code >= 400:
                raise SlackApiError(
                    f"http_{resp.status_code}",
                    method=method,
                    response={"body": resp.text[:300]},
                )

            data_out = resp.json()
            if not isinstance(data_out, dict):
                raise SlackApiError(
                    "invalid_json", method=method, response={"raw": data_out}
                )

            if data_out.get("ok"):
                return data_out

            error = str(data_out.get("error") or "unknown_error")
            if error == "ratelimited":
                last_retry_after = retry_after or float(
                    data_out.get("retry_after") or 1
                )
                if attempt >= self.max_retries:
                    raise SlackRateLimitError(
                        method=method,
                        retry_after=last_retry_after,
                        response=data_out,
                    )
                logger.warning(
                    "slack ratelimited method=%s attempt=%s retry_after=%.1fs",
                    method,
                    attempt + 1,
                    last_retry_after,
                )
                self._sleep(last_retry_after)
                continue

            raise SlackApiError(error, method=method, response=data_out)

        raise SlackRateLimitError(method=method, retry_after=last_retry_after)

    def files_info(self, file_id: str) -> dict[str, Any]:
        """GET files.info for a Slack file id."""
        if not file_id:
            raise ValueError("file_id is required")
        return self.api_call("files.info", params={"file": file_id})

    def download_file(self, url: str) -> bytes:
        """Download a private Slack file URL with the bot token."""
        if not url:
            raise ValueError("url is required")
        headers = {"Authorization": f"Bearer {self.bot_token}"}
        last_retry_after = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    resp = client.get(url, headers=headers)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt >= self.max_retries:
                    raise SlackApiError(
                        f"transport_{type(exc).__name__}",
                        method="files.download",
                        response={"error": str(exc)[:300]},
                    ) from exc
                delay = min(8.0, 0.5 * (2**attempt))
                self._sleep(delay)
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                last_retry_after = _retry_after_seconds(resp)
                if attempt >= self.max_retries:
                    raise SlackRateLimitError(
                        method="files.download",
                        retry_after=last_retry_after,
                    )
                self._sleep(last_retry_after)
                continue

            if resp.status_code >= 400:
                raise SlackApiError(
                    f"http_{resp.status_code}",
                    method="files.download",
                    response={"body": resp.text[:300]},
                )
            return resp.content

        raise SlackRateLimitError(
            method="files.download", retry_after=last_retry_after
        )

    def files_upload(
        self,
        *,
        channels: str,
        filename: str,
        content: bytes,
        title: str | None = None,
        initial_comment: str | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file via files.upload (multipart).

        Requires `files:write`. Prefer channels=channel_id; optional thread_ts
        attaches the file to a thread when the workspace supports it.
        """
        if not channels:
            raise ValueError("channels is required")
        if not filename:
            raise ValueError("filename is required")
        if content is None:
            raise ValueError("content is required")

        form: dict[str, Any] = {"channels": channels, "filename": filename}
        if title:
            form["title"] = title
        if initial_comment:
            form["initial_comment"] = initial_comment
        if thread_ts:
            form["thread_ts"] = thread_ts

        files = {
            "file": (filename, content, "application/octet-stream"),
        }
        return self.api_call_post("files.upload", data=form, files=files)

    def files_edit(
        self,
        *,
        file_id: str,
        title: str,
        filetype: str | None = None,
    ) -> dict[str, Any]:
        """
        Best-effort update of Slack file title via files.edit.

        Slack has no reliable API to change the underlying filename; title
        updates require `files:write` and may still fail on some file types.
        Prefer renaming the tenant-stored org copy when this errors.
        """
        if not file_id:
            raise ValueError("file_id is required")
        if not (title or "").strip():
            raise ValueError("title is required")
        data: dict[str, Any] = {"file": file_id, "title": title.strip()}
        if filetype:
            data["filetype"] = filetype
        return self.api_call_post("files.edit", data=data)

    def conversations_list(
        self,
        *,
        types: str = "public_channel,private_channel",
        exclude_archived: bool = True,
        limit: int = 200,
    ) -> Iterator[dict[str, Any]]:
        """Yield channel objects from conversations.list (all pages)."""
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {
                "types": types,
                "exclude_archived": exclude_archived,
                "limit": limit,
            }
            if cursor:
                params["cursor"] = cursor
            data = self.api_call("conversations.list", params=params)
            for channel in data.get("channels") or []:
                if isinstance(channel, dict):
                    yield channel
            cursor = _next_cursor(data)
            if not cursor:
                break

    def conversations_history(
        self,
        channel: str,
        *,
        oldest: str | None = None,
        latest: str | None = None,
        limit: int = 200,
        inclusive: bool = True,
    ) -> Iterator[dict[str, Any]]:
        """Yield raw message dicts from conversations.history (all pages)."""
        if not channel:
            raise ValueError("channel is required")
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {
                "channel": channel,
                "limit": limit,
                "inclusive": inclusive,
            }
            if oldest is not None:
                params["oldest"] = oldest
            if latest is not None:
                params["latest"] = latest
            if cursor:
                params["cursor"] = cursor
            data = self.api_call("conversations.history", params=params)
            for message in data.get("messages") or []:
                if isinstance(message, dict):
                    yield message
            cursor = _next_cursor(data)
            if not cursor:
                break


def slack_client_for_team(
    db: Session,
    settings: Settings,
    team_id: str,
    **client_kwargs: Any,
) -> SlackWebClient:
    install = get_install_by_team(db, team_id)
    if install is None:
        raise ValueError(f"No Slack install for team_id={team_id}")
    return SlackWebClient(get_bot_token(install, settings), **client_kwargs)


def slack_client_for_tenant(
    db: Session,
    settings: Settings,
    tenant_id: UUID,
    **client_kwargs: Any,
) -> SlackWebClient:
    install = get_install_by_tenant(db, tenant_id)
    if install is None:
        raise ValueError(f"No Slack install for tenant_id={tenant_id}")
    return SlackWebClient(get_bot_token(install, settings), **client_kwargs)


def _stringify_params(params: dict[str, Any] | None) -> dict[str, str]:
    """Slack prefers string form/query values."""
    out: dict[str, str] = {}
    if not params:
        return out
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = str(value)
    return out


def _next_cursor(data: dict[str, Any]) -> Optional[str]:
    meta = data.get("response_metadata") or {}
    if not isinstance(meta, dict):
        return None
    cursor = meta.get("next_cursor") or ""
    if isinstance(cursor, str) and cursor.strip():
        return cursor.strip()
    return None


def _retry_after_seconds(resp: httpx.Response) -> float:
    raw = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
    if raw is None:
        return 1.0
    try:
        return max(float(raw), 0.1)
    except (TypeError, ValueError):
        return 1.0


def _safe_json(resp: httpx.Response) -> dict[str, Any] | None:
    try:
        data = resp.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None
