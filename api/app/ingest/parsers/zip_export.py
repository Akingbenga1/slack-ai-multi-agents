"""Parse official Slack workspace export ZIP → NormalizedMessage."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterator, Mapping

from api.app.ingest.normalize import normalize_slack_message
from api.app.ingest.schema import NormalizedMessage, SourceFormat

# Top-level metadata files in a Slack export (not channel day dumps)
_META_NAMES = frozenset(
    {
        "channels.json",
        "groups.json",
        "dms.json",
        "mpims.json",
        "users.json",
        "integration_logs.json",
        "canvas_posts.json",
        "lists.json",
        "huddle_transcripts.json",
        "file_conversations.json",
    }
)


def _load_channel_name_to_id(zf: zipfile.ZipFile) -> dict[str, str]:
    """Map export folder name → channel id from channels.json / groups.json."""
    mapping: dict[str, str] = {}
    for meta in ("channels.json", "groups.json"):
        try:
            raw = zf.read(_find_member(zf, meta))
        except KeyError:
            continue
        try:
            rows = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            name = row.get("name")
            cid = row.get("id")
            if isinstance(name, str) and name.strip() and isinstance(cid, str) and cid.strip():
                mapping[name.strip()] = cid.strip()
    return mapping


def _find_member(zf: zipfile.ZipFile, basename: str) -> str:
    """Locate ``basename`` at archive root or under a single top folder."""
    names = zf.namelist()
    if basename in names:
        return basename
    for name in names:
        parts = name.replace("\\", "/").split("/")
        if len(parts) == 2 and parts[1] == basename and parts[0]:
            return name
        if parts[-1] == basename and name.count("/") <= 1:
            return name
    raise KeyError(basename)


def _channel_from_member_path(member: str) -> str | None:
    """
    Export day files look like ``general/2020-01-01.json`` or
    ``export_root/general/2020-01-01.json``.
    """
    path = member.replace("\\", "/")
    if path.endswith("/"):
        return None
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return None
    filename = parts[-1]
    if not filename.endswith(".json"):
        return None
    if filename in _META_NAMES:
        return None
    # day file: YYYY-MM-DD.json
    stem = filename[:-5]
    if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
        return parts[-2]
    return None


def iter_slack_export_zip(
    source: str | Path | BinaryIO,
    *,
    source_format: SourceFormat = SourceFormat.SLACK_EXPORT,
) -> Iterator[NormalizedMessage]:
    """
    Yield normalized messages from a Slack export ZIP.

    Channel identity prefers Slack channel id from ``channels.json`` when the
    export folder name matches; otherwise the folder name is used.
    """
    # Path-like vs already-open file
    if isinstance(source, (str, Path)):
        zf_ctx = zipfile.ZipFile(source, "r")
        close = True
    else:
        zf_ctx = zipfile.ZipFile(source, "r")
        close = True

    try:
        zf = zf_ctx
        name_to_id = _load_channel_name_to_id(zf)
        for member in zf.namelist():
            channel_name = _channel_from_member_path(member)
            if not channel_name:
                continue
            channel = name_to_id.get(channel_name, channel_name)
            try:
                raw_bytes = zf.read(member)
                payload = json.loads(raw_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError):
                continue
            if not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, Mapping):
                    continue
                msg = normalize_slack_message(
                    row,
                    channel=channel,
                    source_format=source_format,
                )
                if msg is not None:
                    yield msg
    finally:
        if close:
            zf_ctx.close()
