"""PDF analysis upload deliverable (Sprint 26.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from api.app.logging_config import get_logger
from api.app.slack.client import SlackApiError, SlackWebClient
from api.app.slack.files.refs import (
    AttachedEvidence,
    first_usable_evidence,
    require_client_id,
)
from api.app.slack.pdf_export import analysis_to_pdf_bytes, default_pdf_filename
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import store_upload

logger = get_logger("api.slack.files.pdf")

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

    usable = first_usable_evidence(attached_evidence, client_id=cid)
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
