"""Slack attachment / file-reference intake (Sprint 23.1)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from api.app.ingest.documents.extract import (
    UnsupportedDocumentFormatError,
    extract_document,
)
from api.app.logging_config import get_logger
from api.app.slack.client import SlackApiError, SlackWebClient
from api.app.uploads.roles import DOCUMENT_EXTENSIONS, FileRole
from api.app.uploads.storage import sanitize_filename, store_upload

logger = get_logger("api.slack.attachments")

# Slack file permalink / file_id cues in message text
_FILE_PERMALINK_RE = re.compile(
    r"https?://(?:[a-z0-9.-]+\.)?slack\.com/files/[^/\s]+/([F][A-Z0-9]+)",
    re.I,
)
_FILE_ID_RE = re.compile(r"\b(F[A-Z0-9]{8,})\b")

# Cap extracted text kept on agent state (prompt budget)
_MAX_EVIDENCE_CHARS = 24_000


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


@dataclass
class IntakeResult:
    """Outcome of attachment intake for one event."""

    evidence: list[AttachedEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    refs: list[SlackFileRef] = field(default_factory=list)


def require_client_id(client_id: str | None) -> str:
    value = (client_id or "").strip()
    if not value:
        raise ValueError("client_id is required for Slack attachment intake")
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


def _truncate(text: str, max_chars: int = _MAX_EVIDENCE_CHARS) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 20].rstrip() + "\n…[truncated]"


def _extension_ok(filename: str) -> bool:
    return Path(filename).suffix.lower() in DOCUMENT_EXTENSIONS


def intake_attachments(
    *,
    client_id: str,
    bot_token: str,
    event: dict[str, Any],
    upload_root: Path,
    slack_client: SlackWebClient | None = None,
    max_files: int = 3,
) -> IntakeResult:
    """
    Detect → download → tenant-store → parse attachments on a Slack event.

    Fail-closed on blank client_id. Continues past individual file failures.
    """
    cid = require_client_id(client_id)
    if not bot_token:
        raise ValueError("bot_token is required for Slack attachment intake")

    refs = files_from_event(event)
    result = IntakeResult(refs=refs)
    if not refs:
        return result

    client = slack_client or SlackWebClient(bot_token)
    for ref in refs[:max_files]:
        try:
            evidence = _intake_one(
                client=client,
                client_id=cid,
                ref=ref,
                upload_root=upload_root,
            )
            result.evidence.append(evidence)
        except Exception as exc:
            msg = f"{ref.file_id}: {exc}"
            logger.warning(
                "slack_attachment_intake_failed client_id=%s file_id=%s err=%s",
                cid,
                ref.file_id,
                exc,
            )
            result.errors.append(msg)
            result.evidence.append(
                AttachedEvidence(
                    client_id=cid,
                    file_id=ref.file_id,
                    filename=ref.name or ref.file_id,
                    mimetype=ref.mimetype,
                    text="",
                    parse_error=str(exc)[:300],
                )
            )

    logger.info(
        "slack_attachment_intake client_id=%s refs=%s evidence=%s errors=%s",
        cid,
        len(refs),
        len([e for e in result.evidence if e.text]),
        len(result.errors),
    )
    return result


def _intake_one(
    *,
    client: SlackWebClient,
    client_id: str,
    ref: SlackFileRef,
    upload_root: Path,
) -> AttachedEvidence:
    download_url = ref.url_private_download
    name = ref.name
    mimetype = ref.mimetype

    if not download_url or not name:
        meta = client.files_info(ref.file_id)
        file_obj = meta.get("file") if isinstance(meta, dict) else None
        if not isinstance(file_obj, dict):
            raise SlackApiError("no_file", method="files.info", response=meta)
        name = str(file_obj.get("name") or file_obj.get("title") or ref.file_id)
        mimetype = str(file_obj.get("mimetype") or "") or mimetype
        download_url = str(
            file_obj.get("url_private_download")
            or file_obj.get("url_private")
            or ""
        )

    if not download_url:
        raise SlackApiError(
            "no_download_url",
            method="files.info",
            response={"file_id": ref.file_id},
        )

    filename = sanitize_filename(name or f"{ref.file_id}.bin")
    raw = client.download_file(download_url)

    stored_rel: str | None = None
    try:
        if _extension_ok(filename):
            stored = store_upload(
                upload_root=upload_root,
                client_id=client_id,
                file_role=FileRole.DOCUMENT,
                filename=filename,
                data=raw,
                content_type=mimetype,
            )
            stored_rel = stored.relative_path
        else:
            stored_rel = _store_raw_attachment(
                upload_root=upload_root,
                client_id=client_id,
                filename=filename,
                data=raw,
            )
    except Exception as exc:
        logger.warning(
            "slack_attachment_store_failed client_id=%s file_id=%s err=%s",
            client_id,
            ref.file_id,
            exc,
        )

    text = ""
    unit_count = 0
    parse_error: str | None = None
    try:
        doc = extract_document(raw, filename=filename, content_type=mimetype)
        unit_count = len(doc.units)
        text = _truncate("\n\n".join(u.text for u in doc.units if u.text))
        if not text:
            parse_error = "empty_extract"
    except UnsupportedDocumentFormatError as exc:
        parse_error = str(exc)
    except Exception as exc:
        parse_error = f"parse_failed: {exc}"[:300]

    return AttachedEvidence(
        client_id=client_id,
        file_id=ref.file_id,
        filename=filename,
        mimetype=mimetype,
        text=text,
        stored_relative_path=stored_rel,
        unit_count=unit_count,
        parse_error=parse_error,
        source="slack",
    )


def _store_raw_attachment(
    *,
    upload_root: Path,
    client_id: str,
    filename: str,
    data: bytes,
) -> str:
    """Store unsupported-extension bytes under tenant dir (isolation only)."""
    cid = require_client_id(client_id)
    safe = sanitize_filename(filename)
    upload_id = str(uuid4())
    tenant_dir = Path(upload_root) / cid
    tenant_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{upload_id}_{safe}"
    absolute = tenant_dir / stored_filename
    absolute.write_bytes(data)
    return f"{cid}/{stored_filename}"


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
