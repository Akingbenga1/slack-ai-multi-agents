"""Slack file refs + attached evidence types (Sprint 26.3)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

# Slack file permalink / file_id cues in message text
_FILE_PERMALINK_RE = re.compile(
    r"https?://(?:[a-z0-9.-]+\.)?slack\.com/files/[^/\s]+/([F][A-Z0-9]+)",
    re.I,
)
_FILE_ID_RE = re.compile(r"\b(F[A-Z0-9]{8,})\b")


@dataclass(frozen=True)
class SlackFileRef:
    """Reference to a Slack file (from event.files or text)."""

    file_id: str
    name: str | None = None
    mimetype: str | None = None
    url_private_download: str | None = None
    permalink: str | None = None


@dataclass
class AttachedEvidence:
    """Tenant-scoped parsed attachment ready for agent state."""

    client_id: str
    file_id: str
    filename: str
    mimetype: str | None
    text: str
    stored_relative_path: str | None = None
    unit_count: int = 0
    parse_error: str | None = None
    source: str = "slack"  # slack | text_ref

    def to_chunk(self) -> dict[str, Any]:
        """Shape compatible with retrieved_chunks / format_evidence."""
        label = f"attachment:{self.filename or self.file_id}"
        return {
            "point_id": f"attach:{self.file_id}",
            "score": 1.0,
            "text": self.text,
            "kind": "attachment",
            "client_id": self.client_id,
            "filename": self.filename,
            "locator": self.file_id,
            "title": self.filename,
            "source_format": "slack_attachment",
            "label": label,
            "file_id": self.file_id,
            "stored_relative_path": self.stored_relative_path,
            "parse_error": self.parse_error,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def require_client_id(client_id: str | None) -> str:
    """Fail-closed wrapper; preserves Slack intake ValueError message."""
    from api.app.tenant import ClientIdRequired
    from api.app.tenant import require_client_id as _require_client_id

    try:
        value = _require_client_id(
            client_id,
            message="client_id is required for Slack attachment intake",
        )
    except ClientIdRequired as exc:
        raise ValueError("client_id is required for Slack attachment intake") from exc
    try:
        return str(UUID(value))
    except (TypeError, ValueError):
        return value


def files_from_event(event: dict[str, Any]) -> list[SlackFileRef]:
    """
    Collect file refs from event['files'] and text permalinks / file ids.

    Dedupes by file_id (event.files win over text-only refs).
    """
    by_id: dict[str, SlackFileRef] = {}

    raw_files = event.get("files") or []
    if isinstance(raw_files, list):
        for item in raw_files:
            if not isinstance(item, dict):
                continue
            fid = str(item.get("id") or "").strip()
            if not fid:
                continue
            by_id[fid] = SlackFileRef(
                file_id=fid,
                name=str(item.get("name") or item.get("title") or "") or None,
                mimetype=str(item.get("mimetype") or "") or None,
                url_private_download=(
                    str(
                        item.get("url_private_download")
                        or item.get("url_private")
                        or ""
                    )
                    or None
                ),
                permalink=str(item.get("permalink") or "") or None,
            )

    text = str(event.get("text") or "")
    for match in _FILE_PERMALINK_RE.finditer(text):
        fid = match.group(1)
        if fid not in by_id:
            by_id[fid] = SlackFileRef(file_id=fid, permalink=match.group(0))
    for match in _FILE_ID_RE.finditer(text):
        fid = match.group(1)
        if fid not in by_id:
            by_id[fid] = SlackFileRef(file_id=fid)

    return list(by_id.values())


def evidence_has_usable_text(
    evidence: list[AttachedEvidence] | list[dict[str, Any]],
) -> bool:
    """True when at least one attachment has non-empty extracted text."""
    for item in evidence or []:
        if isinstance(item, AttachedEvidence):
            if (item.text or "").strip():
                return True
        elif isinstance(item, dict):
            if (item.get("text") or "").strip():
                return True
    return False


def evidence_to_chunks(
    evidence: list[AttachedEvidence] | list[dict[str, Any]],
    *,
    client_id: str,
) -> list[dict[str, Any]]:
    """Convert attached evidence into retrieved_chunks-shaped dicts."""
    cid = require_client_id(client_id)
    out: list[dict[str, Any]] = []
    for item in evidence or []:
        if isinstance(item, AttachedEvidence):
            if item.client_id != cid:
                continue
            chunk = item.to_chunk()
            if chunk.get("text"):
                out.append(chunk)
        elif isinstance(item, dict):
            if (item.get("client_id") or "").strip() != cid:
                continue
            text = (item.get("text") or "").strip()
            if not text:
                continue
            out.append(
                {
                    "point_id": item.get("point_id")
                    or f"attach:{item.get('file_id')}",
                    "score": float(item.get("score") or 1.0),
                    "text": text,
                    "kind": item.get("kind") or "attachment",
                    "client_id": cid,
                    "filename": item.get("filename"),
                    "locator": item.get("locator") or item.get("file_id"),
                    "title": item.get("title") or item.get("filename"),
                    "source_format": item.get("source_format") or "slack_attachment",
                    "label": item.get("label")
                    or f"attachment:{item.get('filename') or item.get('file_id')}",
                    "file_id": item.get("file_id"),
                    "stored_relative_path": item.get("stored_relative_path"),
                }
            )
    return out


def first_usable_evidence(
    evidence: list[AttachedEvidence] | list[dict[str, Any]],
    *,
    client_id: str,
) -> AttachedEvidence | dict[str, Any] | None:
    """Prefer same-tenant attachment with text; else any same-tenant attachment."""
    cid = require_client_id(client_id)
    for item in evidence or []:
        if isinstance(item, AttachedEvidence):
            if item.client_id == cid and (item.text or "").strip():
                return item
        elif isinstance(item, dict):
            if (item.get("client_id") or "").strip() == cid and (
                item.get("text") or ""
            ).strip():
                return item
    for item in evidence or []:
        if isinstance(item, AttachedEvidence) and item.client_id == cid:
            return item
        if isinstance(item, dict) and (item.get("client_id") or "").strip() == cid:
            return item
    return None
