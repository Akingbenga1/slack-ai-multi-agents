"""Per-channel Slack sync watermarks in Postgres."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import SyncWatermark

SOURCE_SLACK_HISTORY = "slack_history"
SOURCE_SLACK_LIVE = "slack_live"
SOURCE_DOCUMENTS = "documents"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_slack_ts(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ts_min(a: str | None, b: str | None) -> str | None:
    fa, fb = parse_slack_ts(a), parse_slack_ts(b)
    if fa is None:
        return b if fb is not None else a
    if fb is None:
        return a
    return a if fa <= fb else b


def ts_max(a: str | None, b: str | None) -> str | None:
    fa, fb = parse_slack_ts(a), parse_slack_ts(b)
    if fa is None:
        return b if fb is not None else a
    if fb is None:
        return a
    return a if fa >= fb else b


def bounds_from_watermark(row: SyncWatermark | None) -> tuple[Optional[str], Optional[str]]:
    """Return (oldest, latest) Slack ts from meta / cursor."""
    if row is None:
        return None, None
    meta = row.meta if isinstance(row.meta, dict) else {}
    oldest = meta.get("oldest")
    latest = meta.get("latest")
    if latest is None and row.cursor:
        latest = row.cursor
    oldest_s = str(oldest) if oldest is not None else None
    latest_s = str(latest) if latest is not None else None
    return oldest_s, latest_s


def get_watermark(
    db: Session,
    *,
    tenant_id: UUID,
    channel_id: str,
    source: str = SOURCE_SLACK_LIVE,
) -> Optional[SyncWatermark]:
    return db.scalar(
        select(SyncWatermark).where(
            SyncWatermark.tenant_id == tenant_id,
            SyncWatermark.source == source,
            SyncWatermark.channel_id == channel_id,
        )
    )


def list_watermarks(
    db: Session,
    *,
    tenant_id: UUID,
    source: str = SOURCE_SLACK_LIVE,
) -> list[SyncWatermark]:
    return list(
        db.scalars(
            select(SyncWatermark).where(
                SyncWatermark.tenant_id == tenant_id,
                SyncWatermark.source == source,
            )
        )
    )


def upsert_watermark(
    db: Session,
    *,
    tenant_id: UUID,
    channel_id: str,
    source: str = SOURCE_SLACK_LIVE,
    oldest: str | None = None,
    latest: str | None = None,
    last_synced_at: datetime | None = None,
    merge: bool = True,
    extra_meta: dict[str, Any] | None = None,
) -> SyncWatermark:
    """
    Create or update a per-channel watermark.

    When ``merge`` is True (default): keep the earliest ``oldest`` and latest ``latest``.
    ``cursor`` mirrors ``latest`` for a single high-water string sync can pass as
    ``conversations.history(oldest=…)``.
    """
    if not channel_id:
        raise ValueError("channel_id is required")

    row = get_watermark(db, tenant_id=tenant_id, channel_id=channel_id, source=source)
    prev_oldest, prev_latest = bounds_from_watermark(row)

    if merge and row is not None:
        next_oldest = ts_min(prev_oldest, oldest) if oldest is not None else prev_oldest
        next_latest = ts_max(prev_latest, latest) if latest is not None else prev_latest
    else:
        next_oldest = oldest if oldest is not None else prev_oldest
        next_latest = latest if latest is not None else prev_latest

    meta: dict[str, Any] = {}
    if row is not None and isinstance(row.meta, dict):
        meta.update(row.meta)
    if extra_meta:
        meta.update(extra_meta)
    if next_oldest is not None:
        meta["oldest"] = next_oldest
    if next_latest is not None:
        meta["latest"] = next_latest

    synced_at = last_synced_at or _utcnow()

    if row is None:
        row = SyncWatermark(
            tenant_id=tenant_id,
            source=source,
            channel_id=channel_id,
            cursor=next_latest,
            last_synced_at=synced_at,
            meta=meta or None,
        )
        db.add(row)
    else:
        row.cursor = next_latest
        row.last_synced_at = synced_at
        row.meta = meta or None

    db.commit()
    db.refresh(row)
    return row
