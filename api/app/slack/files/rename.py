"""Rename Slack title / org-stored copy (Sprint 26.3)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from api.app.blob_store import resolve_blob_store
from api.app.blob_store.provider import BlobStore
from api.app.logging_config import get_logger
from api.app.slack.client import SlackApiError, SlackWebClient
from api.app.slack.files.refs import (
    AttachedEvidence,
    first_usable_evidence,
    require_client_id,
)
from api.app.uploads.storage import sanitize_filename

logger = get_logger("api.slack.files.rename")

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

_FILE_RENAME_BROAD_RE = re.compile(
    r"("
    r"\brename\b|"
    r"\b(change|update)\s+(the\s+)?(file\s+)?name\b|"
    r"\bfile_rename\b"
    r")",
    re.I,
)


def question_requests_rename(question: str) -> bool:
    """True when the ask includes a file-rename intent (combined asks)."""
    return bool(_FILE_RENAME_BROAD_RE.search(question or ""))


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
    upload_root: Path | None = None,
    stored_relative_path: str,
    new_filename: str,
    blob_store: BlobStore | None = None,
) -> dict[str, Any]:
    """
    Rename a tenant-scoped stored blob. Fail-closed on path escape /
    wrong tenant prefix.
    """
    cid = require_client_id(client_id)
    rel = (stored_relative_path or "").strip().replace("\\", "/")
    if not rel:
        raise ValueError("stored_relative_path is required")

    safe_new = sanitize_filename(new_filename)
    if not safe_new:
        raise ValueError("new_filename is required")

    store = resolve_blob_store(upload_root=upload_root, blob_store=blob_store)
    # Tenant-bound resolve rejects ``..`` / cross-tenant prefixes.
    canonical = store.resolve(client_id=cid, key=rel)
    # Probe existence via get (raises FileNotFoundError if missing).
    store.get(client_id=cid, key=canonical)

    old_name = Path(canonical).name
    # Preserve upload_id_ prefix when present (uuid_original.ext)
    parts = old_name.split("_", 1)
    if len(parts) == 2 and len(parts[0]) >= 8:
        stored_filename = f"{parts[0]}_{safe_new}"
    else:
        stored_filename = safe_new

    new_rel = f"{cid}/{stored_filename}"
    if new_rel != canonical:
        store.rename(client_id=cid, key=canonical, new_key=new_rel)

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
    target = first_usable_evidence(attached_evidence or [], client_id=cid)
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
