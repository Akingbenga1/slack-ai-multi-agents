"""Normalize raw Slack-shaped dicts into NormalizedMessage."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from api.app.ingest.schema import NormalizedMessage, SourceFormat

# Slack system subtypes that rarely help RAG; still keep if they have real text.
_SKIP_SUBTYPES = frozenset(
    {
        "channel_join",
        "channel_leave",
        "channel_topic",
        "channel_purpose",
        "channel_name",
        "channel_archive",
        "channel_unarchive",
        "group_join",
        "group_leave",
        "group_topic",
        "group_purpose",
        "group_name",
        "group_archive",
        "group_unarchive",
        "bot_add",
        "bot_remove",
        "pinned_item",
        "unpinned_item",
    }
)


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Slack ts sometimes arrives as float in loose dumps
        text = str(value)
        return text
    text = str(value).strip()
    return text or None


def _message_text(raw: Mapping[str, Any]) -> Optional[str]:
    text = _as_str(raw.get("text"))
    if text:
        return text
    # conversations.history sometimes nests blocks-only; keep simple for v1
    return None


def normalize_slack_message(
    raw: Mapping[str, Any] | None,
    *,
    source_format: SourceFormat | str,
    channel: str | None = None,
) -> NormalizedMessage | None:
    """
    Map a Slack message object to NormalizedMessage.

    ``channel`` may be supplied by the parser (export folder / API context)
    when the raw object lacks ``channel`` / ``channel_id``.

    Returns None when the row should be skipped (not a usable message).
    """
    if not raw or not isinstance(raw, Mapping):
        return None

    fmt = SourceFormat(source_format) if not isinstance(source_format, SourceFormat) else source_format

    msg_type = _as_str(raw.get("type")) or "message"
    if msg_type != "message":
        return None

    subtype = _as_str(raw.get("subtype"))
    text = _message_text(raw)
    if not text:
        return None
    if subtype in _SKIP_SUBTYPES:
        # Joins etc. often have templated text; skip for knowledge quality
        return None

    channel_id = (
        _as_str(channel)
        or _as_str(raw.get("channel"))
        or _as_str(raw.get("channel_id"))
    )
    ts = _as_str(raw.get("ts"))
    if not channel_id or not ts:
        return None

    user = _as_str(raw.get("user")) or _as_str(raw.get("user_id"))
    # Bot messages may use bot_id only
    if not user:
        user = _as_str(raw.get("bot_id"))

    thread_ts = _as_str(raw.get("thread_ts"))
    # Parent messages sometimes set thread_ts == ts; keep as None for clarity
    if thread_ts and thread_ts == ts:
        thread_ts = None

    try:
        return NormalizedMessage(
            channel=channel_id,
            ts=ts,
            user=user,
            text=text,
            thread_ts=thread_ts,
            source_format=fmt,
        )
    except Exception:
        return None
