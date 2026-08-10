"""Slack file deliverables: PDF upload + rename + confirmation copy (Sprint 23.3–23.4)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import UUID

from api.app.logging_config import get_logger
from api.app.slack.attachments import AttachedEvidence, require_client_id
from api.app.slack.client import SlackApiError, SlackWebClient
from api.app.slack.pdf_export import analysis_to_pdf_bytes, default_pdf_filename
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import resolve_stored_path, sanitize_filename, store_upload

logger = get_logger("api.slack.file_actions")

MSG_PDF_OK = (
    "PDF deliverable uploaded: *{filename}*"
    "{link_part}. Analysis is grounded in your attached file"
    "{rag_part}."
)
MSG_PDF_UPLOAD_FAILED = (
    "I prepared the analysis PDF (*{filename}*) but Slack upload failed "
    "({error}). An admin may need to reinstall the app with `files:write`, "
    "or try again shortly. The analysis text is still in this reply."
)
MSG_PDF_NO_ATTACHMENT = (
    "I can't produce a file-grounded PDF without an attached or referenced "
    "document. Attach a PDF/DOCX/XLSX/CSV and ask again."
)
MSG_FILE_JOB_DENIED = (
    "Your organisation can't run file/PDF jobs right now ({reason}). "
    "Ask an admin to check plan, entitlements, or daily job budget in the "
    "org portal."
)
MSG_RENAME_OK = (
    "Renamed *{old_name}* → *{new_name}* "
    "({where})."
)
MSG_RENAME_PARTIAL = (
    "Renamed the org-stored copy to *{new_name}* "
    "(path `{path}`). Slack title update did not apply ({slack_error}) — "
    "Slack has no full filename rename API; an admin may need `files:write` "
    "and a reinstall for title edits."
)
MSG_RENAME_NO_TARGET = (
    "I couldn't rename anything — attach or reference a file first, "
    "or ensure the org copy was stored during intake."
)
MSG_RENAME_FAILED = (
    "Rename failed ({error}). Ask an admin to check `files:write` scopes "
    "and tenant upload storage."
)

# "rename … to Q3-final.pdf" / "rename the file as report_v2.csv"
_RENAME_TO_RE = re.compile(
    r"(?:rename|name)\s+(?:.+?\s+)?(?:to|as)\s+[\"'`]?"
    r"([A-Za-z0-9][A-Za-z0-9._\- ]{0,160}\.[A-Za-z0-9]{1,12})"
    r"[\"'`]?",
    re.I,
)
_RENAME_INTENT_RE = re.compile(
    r"("
    r"\brename\b|"
    r"\b(change|update)\s+(the\s+)?(file\s+)?name\b|"
    r"\bfile_rename\b"
    r")",
    re.I,
)


def produce_and_upload_analysis_pdf(
    *,
    client_id: str,
    bot_token: str,
    channel: str,
    analysis_text: str,
    attached_evidence: list[AttachedEvidence] | list[dict[str, Any]],
    upload_root: Path,
    thread_ts: str | None = None,
    title: str | None = None,
    used_rag: bool = False,
    slack_client: SlackWebClient | None = None,
) -> dict[str, Any]:
    """
    Build PDF from analysis, store under tenant upload root, upload to Slack.

    Returns a result dict with ok, filename, permalink, confirmation message,
    and optional error. Fail-closed on blank client_id.
    """
    cid = require_client_id(client_id)
    if not bot_token:
        raise ValueError("bot_token is required for PDF upload")
    if not channel:
        raise ValueError("channel is required for PDF upload")

    usable = _first_usable(attached_evidence, client_id=cid)
    if usable is None and not (analysis_text or "").strip():
        return {
            "ok": False,
            "error": "no_attachment",
            "confirmation": MSG_PDF_NO_ATTACHMENT,
        }

    source_name = None
    if usable is not None:
        source_name = (
            usable.filename
            if isinstance(usable, AttachedEvidence)
            else str(usable.get("filename") or "")
        ) or None

    filename = default_pdf_filename(source_filename=source_name, prefix="competitor_analysis")
    pdf_title = (title or "Competitor analysis").strip() or "Competitor analysis"
    subtitle = f"Source: {source_name}" if source_name else None
    pdf_bytes = analysis_to_pdf_bytes(
        title=pdf_title,
        body=analysis_text or "(empty analysis)",
        subtitle=subtitle,
    )

    stored_rel: str | None = None
    try:
        stored = store_upload(
            upload_root=upload_root,
            client_id=cid,
            file_role=FileRole.DOCUMENT,
            filename=filename,
            data=pdf_bytes,
            content_type="application/pdf",
        )
        stored_rel = stored.relative_path
    except Exception as exc:
        logger.warning(
            "pdf_tenant_store_failed client_id=%s err=%s",
            cid,
            exc,
        )

    client = slack_client or SlackWebClient(bot_token)
    try:
        uploaded = client.files_upload(
            channels=channel,
            filename=filename,
            content=pdf_bytes,
            title=pdf_title,
            initial_comment=None,
            thread_ts=thread_ts,
        )
    except SlackApiError as exc:
        logger.warning(
            "pdf_slack_upload_failed client_id=%s error=%s",
            cid,
            exc.error,
        )
        return {
            "ok": False,
            "error": exc.error,
            "filename": filename,
            "stored_relative_path": stored_rel,
            "confirmation": MSG_PDF_UPLOAD_FAILED.format(
                filename=filename,
                error=exc.error,
            ),
            "client_id": cid,
        }

    file_obj = uploaded.get("file") if isinstance(uploaded, dict) else None
    permalink = ""
    slack_file_id = ""
    if isinstance(file_obj, dict):
        permalink = str(file_obj.get("permalink") or "")
        slack_file_id = str(file_obj.get("id") or "")

    link_part = f" — <{permalink}|open PDF>" if permalink else ""
    rag_part = " (plus org knowledge)" if used_rag else ""
    confirmation = MSG_PDF_OK.format(
        filename=filename,
        link_part=link_part,
        rag_part=rag_part,
    )
    logger.info(
        "pdf_upload_ok client_id=%s file_id=%s filename=%s",
        cid,
        slack_file_id,
        filename,
    )
    return {
        "ok": True,
        "filename": filename,
        "permalink": permalink,
        "slack_file_id": slack_file_id,
        "stored_relative_path": stored_rel,
        "confirmation": confirmation,
        "client_id": str(UUID(str(cid))),
    }


def _first_usable(
    evidence: list[AttachedEvidence] | list[dict[str, Any]],
    *,
    client_id: str,
) -> AttachedEvidence | dict[str, Any] | None:
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
    # Prefer any same-tenant attachment even without text (for naming)
    for item in evidence or []:
        if isinstance(item, AttachedEvidence) and item.client_id == cid:
            return item
        if isinstance(item, dict) and (item.get("client_id") or "").strip() == cid:
            return item
    return None


def question_requests_rename(question: str) -> bool:
    """True when the ask includes a file-rename intent (J10 combined asks)."""
    return bool(_RENAME_INTENT_RE.search(question or ""))


def parse_requested_filename(
    question: str,
    *,
    fallback_from: str | None = None,
) -> str:
    """
    Extract a new filename from “rename … to X.ext”; else derive a safe default.
    """
    text = (question or "").strip()
    match = _RENAME_TO_RE.search(text)
    if match:
        return sanitize_filename(match.group(1).strip())

    base = sanitize_filename(fallback_from or "attachment.bin")
    stem = Path(base).stem or "attachment"
    suffix = Path(base).suffix or ".bin"
    return sanitize_filename(f"{stem}_renamed{suffix}")


def rename_stored_org_copy(
    *,
    client_id: str,
    upload_root: Path,
    stored_relative_path: str,
    new_filename: str,
) -> dict[str, Any]:
    """
    Rename a tenant-scoped stored file on disk. Fail-closed on path escape /
    wrong tenant prefix.
    """
    cid = require_client_id(client_id)
    rel = (stored_relative_path or "").strip().replace("\\", "/")
    if not rel:
        raise ValueError("stored_relative_path is required")
    if not rel.startswith(f"{cid}/"):
        raise ValueError("stored path is not under this tenant")

    safe_new = sanitize_filename(new_filename)
    if not safe_new:
        raise ValueError("new_filename is required")

    absolute = resolve_stored_path(upload_root, rel)
    if not absolute.is_file():
        raise FileNotFoundError(f"stored file missing: {rel}")

    old_name = absolute.name
    # Preserve upload_id_ prefix when present (uuid_original.ext)
    parts = old_name.split("_", 1)
    if len(parts) == 2 and len(parts[0]) >= 8:
        stored_filename = f"{parts[0]}_{safe_new}"
    else:
        stored_filename = safe_new

    dest = absolute.with_name(stored_filename)
    if dest.resolve() != absolute.resolve():
        # Reject escape even after with_name
        dest_resolved = dest.resolve()
        root = Path(upload_root).resolve()
        if not str(dest_resolved).startswith(str(root / cid)):
            raise ValueError("rename would escape tenant upload root")
        if dest.exists():
            raise FileExistsError(f"target already exists: {stored_filename}")
        absolute.rename(dest)

    new_rel = f"{cid}/{stored_filename}"
    return {
        "ok": True,
        "old_relative_path": rel,
        "stored_relative_path": new_rel,
        "old_filename": old_name,
        "new_filename": safe_new,
        "client_id": cid,
    }


def rename_slack_file_or_copy(
    *,
    client_id: str,
    upload_root: Path,
    new_filename: str | None = None,
    question: str | None = None,
    attached_evidence: list[AttachedEvidence] | list[dict[str, Any]] | None = None,
    file_id: str | None = None,
    stored_relative_path: str | None = None,
    bot_token: str | None = None,
    slack_client: SlackWebClient | None = None,
) -> dict[str, Any]:
    """
    Rename the org-stored copy (primary) and best-effort Slack title via files.edit.

    Slack has no reliable filename rename API; `files.edit` may update title only.
    Fail-closed on blank client_id. Returns confirmation copy for TM-23.
    """
    cid = require_client_id(client_id)
    target = _first_usable(attached_evidence or [], client_id=cid)
    old_name = "attachment"
    slack_file_id = (file_id or "").strip()
    stored_rel = (stored_relative_path or "").strip() or None

    if isinstance(target, AttachedEvidence):
        old_name = target.filename or old_name
        slack_file_id = slack_file_id or target.file_id
        stored_rel = stored_rel or target.stored_relative_path
    elif isinstance(target, dict):
        old_name = str(target.get("filename") or old_name)
        slack_file_id = slack_file_id or str(target.get("file_id") or "")
        stored_rel = stored_rel or (
            str(target.get("stored_relative_path") or "") or None
        )

    requested = (new_filename or "").strip() or parse_requested_filename(
        question or "",
        fallback_from=old_name,
    )
    safe_new = sanitize_filename(requested)

    if not stored_rel and not slack_file_id:
        return {
            "ok": False,
            "error": "no_target",
            "confirmation": MSG_RENAME_NO_TARGET,
            "client_id": cid,
        }

    org_result: dict[str, Any] | None = None
    org_error: str | None = None
    if stored_rel:
        try:
            org_result = rename_stored_org_copy(
                client_id=cid,
                upload_root=upload_root,
                stored_relative_path=stored_rel,
                new_filename=safe_new,
            )
        except Exception as exc:
            org_error = str(exc)[:200]
            logger.warning(
                "rename_org_copy_failed client_id=%s path=%s err=%s",
                cid,
                stored_rel,
                exc,
            )

    slack_ok = False
    slack_error: str | None = None
    if slack_file_id and (bot_token or slack_client is not None):
        client = slack_client or SlackWebClient(bot_token or "")
        try:
            client.files_edit(file_id=slack_file_id, title=safe_new)
            slack_ok = True
        except SlackApiError as exc:
            slack_error = exc.error
            logger.warning(
                "rename_slack_title_failed client_id=%s file_id=%s error=%s",
                cid,
                slack_file_id,
                exc.error,
            )
        except Exception as exc:
            slack_error = str(exc)[:200]
            logger.warning(
                "rename_slack_title_failed client_id=%s file_id=%s err=%s",
                cid,
                slack_file_id,
                exc,
            )
    elif slack_file_id and not bot_token and slack_client is None:
        slack_error = "no_bot_token"

    if org_result and org_result.get("ok") and slack_ok:
        where = "org copy + Slack title"
        confirmation = MSG_RENAME_OK.format(
            old_name=old_name,
            new_name=safe_new,
            where=where,
        )
        return {
            "ok": True,
            "mode": "org_and_slack",
            "old_filename": old_name,
            "new_filename": safe_new,
            "slack_file_id": slack_file_id,
            "stored_relative_path": org_result.get("stored_relative_path"),
            "confirmation": confirmation,
            "client_id": cid,
        }

    if org_result and org_result.get("ok"):
        confirmation = MSG_RENAME_PARTIAL.format(
            new_name=safe_new,
            path=org_result.get("stored_relative_path"),
            slack_error=slack_error or "skipped",
        )
        if not slack_file_id:
            confirmation = MSG_RENAME_OK.format(
                old_name=old_name,
                new_name=safe_new,
                where="org-stored copy",
            )
        return {
            "ok": True,
            "mode": "org_copy",
            "old_filename": old_name,
            "new_filename": safe_new,
            "slack_file_id": slack_file_id or None,
            "stored_relative_path": org_result.get("stored_relative_path"),
            "slack_error": slack_error,
            "confirmation": confirmation,
            "client_id": cid,
        }

    if slack_ok:
        confirmation = MSG_RENAME_OK.format(
            old_name=old_name,
            new_name=safe_new,
            where="Slack title (org copy unavailable)",
        )
        return {
            "ok": True,
            "mode": "slack_title",
            "old_filename": old_name,
            "new_filename": safe_new,
            "slack_file_id": slack_file_id,
            "org_error": org_error,
            "confirmation": confirmation,
            "client_id": cid,
        }

    err = org_error or slack_error or "unknown"
    return {
        "ok": False,
        "error": err,
        "old_filename": old_name,
        "new_filename": safe_new,
        "slack_file_id": slack_file_id or None,
        "confirmation": MSG_RENAME_FAILED.format(error=err),
        "client_id": cid,
    }
