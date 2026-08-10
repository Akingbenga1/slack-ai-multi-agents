"""Live Slack history sync: Web API → normalize → ingest → watermarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.ingest import SourceFormat, normalize_slack_message
from api.app.ingest.pipeline import IngestResult, ingest_messages
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings
from api.app.slack.client import SlackWebClient, slack_client_for_tenant
from api.app.slack.watermarks import (
    SOURCE_SLACK_LIVE,
    bounds_from_watermark,
    get_watermark,
    ts_max,
    ts_min,
    upsert_watermark,
)

logger = get_logger("api.slack.sync")


class _HistoryClient(Protocol):
    def conversations_list(self, **kwargs: Any) -> Any: ...

    def conversations_history(self, channel: str, **kwargs: Any) -> Any: ...


@dataclass
class ChannelSyncResult:
    channel_id: str
    message_count: int = 0
    chunk_count: int = 0
    oldest: Optional[str] = None
    latest: Optional[str] = None
    skipped: bool = False


@dataclass
class SlackSyncResult:
    client_id: str
    channels: list[ChannelSyncResult] = field(default_factory=list)
    message_count: int = 0
    chunk_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "message_count": self.message_count,
            "chunk_count": self.chunk_count,
            "channel_count": len(self.channels),
            "channels": [
                {
                    "channel_id": c.channel_id,
                    "message_count": c.message_count,
                    "chunk_count": c.chunk_count,
                    "oldest": c.oldest,
                    "latest": c.latest,
                    "skipped": c.skipped,
                }
                for c in self.channels
            ],
        }


def sync_slack_history(
    db: Session,
    *,
    tenant_id: UUID,
    channel_ids: Sequence[str] | None = None,
    settings: Settings | None = None,
    client: SlackWebClient | _HistoryClient | None = None,
    ingest_fn: Any = ingest_messages,
) -> SlackSyncResult:
    """
    Incremental pull for one tenant: conversations → WEB_API normalize → ingest.

    Uses ``sync_watermarks`` ``latest`` as ``conversations.history(oldest=…)``.
    """
    settings = settings or get_settings()
    slack: SlackWebClient | _HistoryClient
    if client is None:
        slack = slack_client_for_tenant(db, settings, tenant_id)
    else:
        slack = client

    if channel_ids is None:
        channels = [str(ch["id"]) for ch in slack.conversations_list() if ch.get("id")]
    else:
        channels = [str(c) for c in channel_ids if c]

    result = SlackSyncResult(client_id=str(tenant_id))
    for channel_id in channels:
        channel_result = _sync_channel(
            db,
            tenant_id=tenant_id,
            channel_id=channel_id,
            slack=slack,
            settings=settings,
            ingest_fn=ingest_fn,
        )
        result.channels.append(channel_result)
        result.message_count += channel_result.message_count
        result.chunk_count += channel_result.chunk_count

    logger.info(
        "slack sync done client_id=%s channels=%s messages=%s chunks=%s",
        tenant_id,
        len(result.channels),
        result.message_count,
        result.chunk_count,
    )
    return result


def _sync_channel(
    db: Session,
    *,
    tenant_id: UUID,
    channel_id: str,
    slack: SlackWebClient | _HistoryClient,
    settings: Settings,
    ingest_fn: Any,
) -> ChannelSyncResult:
    row = get_watermark(
        db,
        tenant_id=tenant_id,
        channel_id=channel_id,
        source=SOURCE_SLACK_LIVE,
    )
    _, latest = bounds_from_watermark(row)

    messages = []
    batch_oldest: str | None = None
    batch_latest: str | None = None
    for raw in slack.conversations_history(channel_id, oldest=latest):
        msg = normalize_slack_message(
            raw,
            channel=channel_id,
            source_format=SourceFormat.WEB_API,
        )
        if msg is None:
            continue
        messages.append(msg)
        batch_oldest = ts_min(batch_oldest, msg.ts)
        batch_latest = ts_max(batch_latest, msg.ts)

    if not messages:
        # Touch last_synced_at even when idle so status API can show progress later.
        upsert_watermark(
            db,
            tenant_id=tenant_id,
            channel_id=channel_id,
            source=SOURCE_SLACK_LIVE,
        )
        return ChannelSyncResult(channel_id=channel_id, skipped=True)

    ingest_result: IngestResult = ingest_fn(
        client_id=str(tenant_id),
        messages=messages,
        settings=settings,
    )
    upsert_watermark(
        db,
        tenant_id=tenant_id,
        channel_id=channel_id,
        source=SOURCE_SLACK_LIVE,
        oldest=batch_oldest,
        latest=batch_latest,
    )
    return ChannelSyncResult(
        channel_id=channel_id,
        message_count=ingest_result.message_count,
        chunk_count=ingest_result.chunk_count,
        oldest=batch_oldest,
        latest=batch_latest,
    )
