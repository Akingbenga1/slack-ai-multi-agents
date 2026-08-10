"""Slack attachment intake — download / store / parse (Sprint 26.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from api.app.ingest.documents.extract import (
    UnsupportedDocumentFormatError,
    extract_document,
)
from api.app.logging_config import get_logger
from api.app.slack.client import SlackApiError, SlackWebClient
from api.app.slack.files.refs import (
    AttachedEvidence,
    SlackFileRef,
    files_from_event,
    require_client_id,
)
from api.app.uploads.roles import DOCUMENT_EXTENSIONS, FileRole
from api.app.uploads.storage import sanitize_filename, store_upload

logger = get_logger("api.slack.files.intake")

# Cap extracted text kept on agent state (prompt budget)
_MAX_EVIDENCE_CHARS = 24_000


@dataclass
class IntakeResult:
    """Outcome of attachment intake for one event."""

    evidence: list[AttachedEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    refs: list[SlackFileRef] = field(default_factory=list)


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


def _truncate(text: str, max_chars: int = _MAX_EVIDENCE_CHARS) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 20].rstrip() + "\n…[truncated]"


def _extension_ok(filename: str) -> bool:
    return Path(filename).suffix.lower() in DOCUMENT_EXTENSIONS


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
