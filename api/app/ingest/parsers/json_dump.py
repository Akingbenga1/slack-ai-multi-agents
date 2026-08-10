"""Parse API-dump shaped JSON / NDJSON → NormalizedMessage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping, TextIO, Union

from api.app.ingest.normalize import normalize_slack_message
from api.app.ingest.schema import NormalizedMessage, SourceFormat

PathLike = Union[str, Path]
Readable = Union[PathLike, TextIO, BinaryIO, bytes, str]


class MissingChannelError(ValueError):
    """Raised when a dump has no channel and no override was provided."""


def _read_text(source: Readable) -> str:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source).decode("utf-8")
    if isinstance(source, Path):
        return source.read_text(encoding="utf-8")
    if isinstance(source, str):
        # Existing file path vs inline JSON / NDJSON text
        path = Path(source)
        if "\n" not in source and path.is_file():
            return path.read_text(encoding="utf-8")
        return source
    # file-like
    data = source.read()
    if isinstance(data, bytes):
        return data.decode("utf-8")
    return str(data)


def _channel_from_obj(obj: Mapping[str, Any]) -> str | None:
    for key in ("channel", "channel_id"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, Mapping):
            cid = val.get("id")
            if isinstance(cid, str) and cid.strip():
                return cid.strip()
    return None


def _iter_from_messages(
    messages: list[Any],
    *,
    channel: str | None,
    source_format: SourceFormat,
    require_channel: bool,
) -> Iterator[NormalizedMessage]:
    if require_channel and not channel:
        raise MissingChannelError(
            "message list has no channel; pass channel= override or include "
            "channel/channel_id on each message / wrapper"
        )
    for row in messages:
        if not isinstance(row, Mapping):
            continue
        row_channel = _channel_from_obj(row) or channel
        msg = normalize_slack_message(
            row,
            channel=row_channel,
            source_format=source_format,
        )
        if msg is not None:
            yield msg


def _iter_payload(
    payload: Any,
    *,
    channel: str | None,
    source_format: SourceFormat,
) -> Iterator[NormalizedMessage]:
    """
    Accept:
    - ``[ message, ... ]``
    - ``{ "channel": "C…", "messages": [ ... ] }``  (conversations.history style)
    - ``[ { "channel", "messages" }, ... ]``
    - single message object ``{ "type": "message", "ts": ..., ... }``
    """
    if isinstance(payload, list):
        if not payload:
            return
        first = payload[0]
        if isinstance(first, Mapping) and "messages" in first:
            for block in payload:
                if not isinstance(block, Mapping):
                    continue
                block_channel = _channel_from_obj(block) or channel
                messages = block.get("messages")
                if not isinstance(messages, list):
                    continue
                yield from _iter_from_messages(
                    messages,
                    channel=block_channel,
                    source_format=source_format,
                    require_channel=True,
                )
            return
        # Flat message array
        yield from _iter_from_messages(
            payload,
            channel=channel,
            source_format=source_format,
            require_channel=channel is None
            and not any(isinstance(r, Mapping) and _channel_from_obj(r) for r in payload),
        )
        return

    if isinstance(payload, Mapping):
        if "messages" in payload:
            block_channel = _channel_from_obj(payload) or channel
            messages = payload.get("messages")
            if isinstance(messages, list):
                yield from _iter_from_messages(
                    messages,
                    channel=block_channel,
                    source_format=source_format,
                    require_channel=True,
                )
            return
        # Single message object
        row_channel = _channel_from_obj(payload) or channel
        if not row_channel:
            raise MissingChannelError(
                "single message has no channel; pass channel= override"
            )
        msg = normalize_slack_message(
            payload,
            channel=row_channel,
            source_format=source_format,
        )
        if msg is not None:
            yield msg
        return

    raise ValueError(f"unsupported JSON payload type: {type(payload).__name__}")


def iter_json_messages(
    source: Readable,
    *,
    channel: str | None = None,
    source_format: SourceFormat = SourceFormat.JSON,
) -> Iterator[NormalizedMessage]:
    """Parse a JSON file/string (array or conversations.history-shaped)."""
    text = _read_text(source)
    payload = json.loads(text)
    yield from _iter_payload(payload, channel=channel, source_format=source_format)


def iter_ndjson_messages(
    source: Readable,
    *,
    channel: str | None = None,
    source_format: SourceFormat = SourceFormat.NDJSON,
) -> Iterator[NormalizedMessage]:
    """
    Parse NDJSON: one JSON object per non-empty line.

    Each line may be a message or a ``{channel, messages}`` wrapper.
    Missing channel without override skips that line (no raise) so a mixed
    stream can continue; use ``channel=`` for dumps without per-row channel.
    """
    text = _read_text(source)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        try:
            yield from _iter_payload(
                payload,
                channel=channel,
                source_format=source_format,
            )
        except MissingChannelError:
            # Per-line skip when channel unknown
            continue
