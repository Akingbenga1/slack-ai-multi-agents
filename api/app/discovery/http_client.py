"""Concrete HTTP discovery client — queries env-configured upstream URLs."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from api.app.discovery.base import (
    DiscoveredTool,
    DiscoveryNotConfiguredError,
    DiscoveryUpstreamError,
    ToolKind,
    service_url_for_kind,
)
from api.app.logging_config import get_logger
from api.app.settings import Settings

logger = get_logger("api.discovery.http_client")


class HttpToolDiscoveryClient:
    """Calls an online discovery service (ARD POST /search) and normalizes results.

    Request body follows Agentic Resource Discovery::
        ``{"query": {"text": "<q>"}, "pageSize": 10}``

    Response rows may use ARD fields (``displayName``, ``identifier``) or
    simpler ``name`` / ``id`` aliases.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def search(self, kind: ToolKind, query: str) -> list[DiscoveredTool]:
        q = (query or "").strip()
        if not q:
            return []

        url = service_url_for_kind(self._settings, kind)
        if not url:
            raise DiscoveryNotConfiguredError(kind)

        timeout = self._settings.discovery_timeout_seconds
        body = {"query": {"text": q}, "pageSize": 10}
        logger.info("discovery_search kind=%s url=%s query_len=%s", kind, url, len(q))

        try:
            with httpx.Client(timeout=timeout, transport=self._transport) as client:
                resp = client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise DiscoveryUpstreamError(
                "discovery upstream timed out",
                code="discovery_upstream_timeout",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            raise DiscoveryUpstreamError(
                "discovery upstream request failed",
                code="discovery_upstream_error",
                status_code=502,
            ) from exc

        if resp.status_code >= 500:
            raise DiscoveryUpstreamError(
                f"discovery upstream returned {resp.status_code}",
                code="discovery_upstream_error",
                status_code=502,
            )
        if resp.status_code >= 400:
            raise DiscoveryUpstreamError(
                f"discovery upstream rejected request ({resp.status_code})",
                code="discovery_upstream_error",
                status_code=502,
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise DiscoveryUpstreamError(
                "discovery upstream returned non-JSON body",
            ) from exc

        return _normalize_payload(payload, kind=kind, default_source=url)


def _normalize_payload(
    payload: Any,
    *,
    kind: ToolKind,
    default_source: str,
) -> list[DiscoveredTool]:
    rows = _extract_rows(payload)
    out: list[DiscoveredTool] = []
    for i, row in enumerate(rows):
        tool = _row_to_tool(row, kind=kind, default_source=default_source, index=i)
        if tool is not None:
            out.append(tool)
    return out


def _extract_rows(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("tools", "results", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _row_to_tool(
    row: Any,
    *,
    kind: ToolKind,
    default_source: str,
    index: int,
) -> Optional[DiscoveredTool]:
    if not isinstance(row, dict):
        return None

    name = str(
        row.get("name")
        or row.get("displayName")
        or row.get("title")
        or ""
    ).strip()
    if not name:
        return None

    tool_id = str(
        row.get("id")
        or row.get("identifier")
        or row.get("slug")
        or f"{kind}-{index}-{name}"
    ).strip()
    summary = str(
        row.get("summary") or row.get("description") or row.get("hint") or ""
    ).strip()
    source = str(row.get("source") or row.get("url") or default_source).strip()

    meta_raw = row.get("metadata")
    metadata: dict[str, Any] = dict(meta_raw) if isinstance(meta_raw, dict) else {}
    skip = {
        "id",
        "identifier",
        "slug",
        "name",
        "displayName",
        "title",
        "summary",
        "description",
        "hint",
        "source",
        "url",
        "metadata",
    }
    for key, value in row.items():
        if key in skip:
            continue
        if key not in metadata:
            metadata[key] = value

    return DiscoveredTool(
        id=tool_id,
        name=name,
        summary=summary,
        source=source,
        kind=kind,
        metadata=metadata,
    )
