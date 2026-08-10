"""Agent guardrails — hedge without evidence; never drop tenant filter (13.4)."""

from __future__ import annotations

from typing import Any

from api.app.tenant import ClientIdRequired
from api.app.tenant import require_client_id as _require_client_id

HEDGE_MESSAGE = (
    "I don't have enough information in your organisation's knowledge base "
    "to answer that confidently. Try rephrasing, or sync Slack history / "
    "upload documents that cover this topic."
)


class TenantContextRequired(ClientIdRequired):
    """Raised when agent state is missing a usable client_id."""


def require_tenant_client_id(client_id: str | None, *, where: str = "agent") -> str:
    """Fail-closed: every agent node must carry a non-empty tenant id."""
    try:
        return _require_client_id(client_id, where=where)
    except ClientIdRequired as exc:
        if isinstance(exc, TenantContextRequired):
            raise
        raise TenantContextRequired(
            f"client_id is required for {where} (tenant filter must never be dropped)"
        ) from exc


def filter_chunks_for_tenant(
    chunks: list[dict[str, Any]] | None,
    client_id: str,
    *,
    min_score: float | None = None,
) -> list[dict[str, Any]]:
    """Keep only tenant-matching chunks; optionally drop weak scores."""
    cid = require_tenant_client_id(client_id, where="filter_chunks_for_tenant")
    out: list[dict[str, Any]] = []
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        if (chunk.get("client_id") or "").strip() != cid:
            continue
        if min_score is not None:
            try:
                score = float(chunk.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            if score < float(min_score):
                continue
        out.append(chunk)
    return out


def should_hedge(chunks: list[dict[str, Any]] | None) -> bool:
    """True when there is no tenant-scoped retrieval evidence."""
    return not bool(chunks)
