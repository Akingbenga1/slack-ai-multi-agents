"""Shared workflow template library (Sprint 24)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.app.db.models import WorkflowTemplate
from api.app.ingest.documents import extract_document
from api.app.ingest.documents.extract import UnsupportedDocumentFormatError
from api.app.logging_config import get_logger
from api.app.uploads.roles import DOCUMENT_EXTENSIONS, FileRole
from api.app.uploads.storage import (
    resolve_stored_path,
    sanitize_filename,
    store_upload,
)

logger = get_logger("api.workflows.library")

VISIBILITY_SHARED = "shared"
VISIBILITY_PERSONAL = "personal"

MSG_NO_CLIENT = "client_id is required"
MSG_NOT_FOUND = "Workflow template not found for this organisation."
MSG_FORBIDDEN_EDIT = "Only the owner can edit this personal workflow draft."
MSG_CROSS_TENANT = "Workflow template is not available for this organisation."


@dataclass(frozen=True)
class StoreResult:
    template: WorkflowTemplate
    created: bool
    ingested_queued: bool = False
    task_id: str | None = None


def require_client_id(client_id: str | None) -> str:
    """Fail-closed wrapper; preserves workflow library ValueError message."""
    from api.app.tenant import ClientIdRequired
    from api.app.tenant import require_client_id as _require_client_id

    try:
        return _require_client_id(client_id, message=MSG_NO_CLIENT)
    except ClientIdRequired as exc:
        raise ValueError(MSG_NO_CLIENT) from exc


def content_hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def title_from_filename(filename: str) -> str:
    base = Path(sanitize_filename(filename)).stem.strip() or "Workflow"
    cleaned = re.sub(r"[_-]+", " ", base).strip()
    return cleaned[:255] or "Workflow"


def extract_workflow_text(
    data: bytes,
    *,
    filename: str,
    content_type: str | None = None,
) -> str:
    """Best-effort text for advice / search; empty string if unreadable."""
    name = sanitize_filename(filename)
    ext = Path(name).suffix.lower()
    try:
        doc = extract_document(data, filename=name, content_type=content_type)
        text = "\n\n".join(u.text for u in doc.units if u.text).strip()
        if text:
            return text[:50_000]
    except UnsupportedDocumentFormatError:
        pass
    except Exception as exc:
        logger.warning("workflow_extract_failed filename=%s err=%s", name, exc)

    if ext in {".md", ".txt", ".text"} or (content_type or "").startswith("text/"):
        try:
            return data.decode("utf-8", errors="replace").strip()[:50_000]
        except Exception:
            return ""
    return ""


def find_shared_by_hash(
    db: Session,
    *,
    client_id: str,
    content_hash: str,
) -> WorkflowTemplate | None:
    cid = UUID(require_client_id(client_id))
    return db.scalar(
        select(WorkflowTemplate).where(
            WorkflowTemplate.tenant_id == cid,
            WorkflowTemplate.content_hash == content_hash,
            WorkflowTemplate.visibility == VISIBILITY_SHARED,
            WorkflowTemplate.parent_id.is_(None),
        )
    )


def find_shared_by_slack_file(
    db: Session,
    *,
    client_id: str,
    source_slack_file_id: str,
) -> WorkflowTemplate | None:
    cid = UUID(require_client_id(client_id))
    fid = (source_slack_file_id or "").strip()
    if not fid:
        return None
    return db.scalar(
        select(WorkflowTemplate).where(
            WorkflowTemplate.tenant_id == cid,
            WorkflowTemplate.source_slack_file_id == fid,
            WorkflowTemplate.visibility == VISIBILITY_SHARED,
            WorkflowTemplate.parent_id.is_(None),
        )
    )


def get_template(
    db: Session,
    *,
    client_id: str,
    template_id: UUID | str,
) -> WorkflowTemplate:
    """Fail-closed tenant-scoped fetch."""
    cid = UUID(require_client_id(client_id))
    tid = UUID(str(template_id))
    row = db.scalar(
        select(WorkflowTemplate).where(
            WorkflowTemplate.id == tid,
            WorkflowTemplate.tenant_id == cid,
        )
    )
    if row is None:
        raise LookupError(MSG_NOT_FOUND)
    return row


def list_templates(
    db: Session,
    *,
    client_id: str,
    q: str | None = None,
    include_personal_for: str | None = None,
    limit: int = 50,
) -> list[WorkflowTemplate]:
    """
    List shared templates for the tenant.

    When ``include_personal_for`` is set, also include that Slack user's
    personal drafts (still tenant-scoped).
    """
    cid = UUID(require_client_id(client_id))
    limit_i = max(1, min(int(limit), 200))
    owner = (include_personal_for or "").strip() or None

    if owner:
        visibility_filter = or_(
            WorkflowTemplate.visibility == VISIBILITY_SHARED,
            (
                (WorkflowTemplate.visibility == VISIBILITY_PERSONAL)
                & (WorkflowTemplate.owner_slack_user_id == owner)
            ),
        )
    else:
        visibility_filter = WorkflowTemplate.visibility == VISIBILITY_SHARED

    stmt = select(WorkflowTemplate).where(
        WorkflowTemplate.tenant_id == cid,
        visibility_filter,
    )

    query = (q or "").strip()
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                WorkflowTemplate.title.ilike(like),
                WorkflowTemplate.original_filename.ilike(like),
                WorkflowTemplate.body_text.ilike(like),
            )
        )

    stmt = stmt.order_by(WorkflowTemplate.updated_at.desc()).limit(limit_i)
    return list(db.scalars(stmt).all())


def store_workflow_template(
    db: Session,
    *,
    client_id: str,
    upload_root: Path,
    filename: str,
    data: bytes,
    title: str | None = None,
    source_slack_file_id: str | None = None,
    created_by_slack_user_id: str | None = None,
    created_by_user_id: UUID | str | None = None,
    content_type: str | None = None,
    body_text: str | None = None,
    enqueue_ingest: bool = False,
    meta: dict[str, Any] | None = None,
) -> StoreResult:
    """
    Persist a shared workflow template under the tenant upload root.

    Idempotent for shared originals: same ``content_hash`` or Slack
    ``file_id`` returns the existing row without duplicating.
    """
    cid_str = require_client_id(client_id)
    cid = UUID(cid_str)
    if not data:
        raise ValueError("empty file")

    digest = content_hash_bytes(data)
    slack_fid = (source_slack_file_id or "").strip() or None

    existing = None
    if slack_fid:
        existing = find_shared_by_slack_file(
            db, client_id=cid_str, source_slack_file_id=slack_fid
        )
    if existing is None:
        existing = find_shared_by_hash(db, client_id=cid_str, content_hash=digest)
    if existing is not None:
        logger.info(
            "workflow_store_idempotent client_id=%s template_id=%s",
            cid_str,
            existing.id,
        )
        return StoreResult(template=existing, created=False)

    stored = store_upload(
        upload_root=upload_root,
        client_id=cid_str,
        file_role=FileRole.WORKFLOW,
        filename=filename,
        data=data,
        content_type=content_type,
    )

    text = body_text
    if text is None:
        text = extract_workflow_text(
            data, filename=stored.original_filename, content_type=content_type
        )

    creator_user: UUID | None = None
    if created_by_user_id:
        creator_user = UUID(str(created_by_user_id))

    row = WorkflowTemplate(
        tenant_id=cid,
        title=(title or title_from_filename(stored.original_filename))[:255],
        source_slack_file_id=slack_fid,
        storage_relative_path=stored.relative_path,
        content_hash=digest,
        original_filename=stored.original_filename,
        body_text=text or None,
        created_by_slack_user_id=(created_by_slack_user_id or "").strip() or None,
        created_by_user_id=creator_user,
        owner_slack_user_id=None,
        visibility=VISIBILITY_SHARED,
        parent_id=None,
        version=1,
        meta={
            **(meta or {}),
            "upload_id": stored.upload_id,
            "file_role": str(FileRole.WORKFLOW),
            "size_bytes": stored.size_bytes,
        },
    )
    db.add(row)
    db.flush()

    ingested = False
    task_id: str | None = None
    if enqueue_ingest and Path(stored.original_filename).suffix.lower() in DOCUMENT_EXTENSIONS:
        try:
            from worker.tasks import enqueue_ingest_upload

            async_result = enqueue_ingest_upload(
                client_id=cid_str,
                relative_path=stored.relative_path,
                filename=stored.original_filename,
                file_role=FileRole.WORKFLOW,
                upload_id=stored.upload_id,
            )
            task_id = getattr(async_result, "id", None)
            ingested = True
            meta_out = dict(row.meta or {})
            meta_out["ingest_task_id"] = task_id
            row.meta = meta_out
            db.flush()
        except Exception as exc:
            logger.warning(
                "workflow_ingest_enqueue_failed client_id=%s err=%s",
                cid_str,
                exc,
            )

    logger.info(
        "workflow_stored client_id=%s template_id=%s hash=%s",
        cid_str,
        row.id,
        digest[:12],
    )
    return StoreResult(
        template=row,
        created=True,
        ingested_queued=ingested,
        task_id=task_id,
    )


def store_from_attached_evidence(
    db: Session,
    *,
    client_id: str,
    upload_root: Path,
    evidence: dict[str, Any],
    title: str | None = None,
    created_by_slack_user_id: str | None = None,
    enqueue_ingest: bool = False,
) -> StoreResult:
    """
    Store a shared template from Sprint 23.1 attached evidence.

    Reads bytes from the tenant-scoped stored path when present.
    """
    cid = require_client_id(client_id)
    if str(evidence.get("client_id") or "") != cid:
        raise PermissionError(MSG_CROSS_TENANT)

    rel = str(evidence.get("stored_relative_path") or "").strip()
    if not rel:
        raise ValueError("attachment has no stored path")
    try:
        absolute = resolve_stored_path(upload_root, rel, client_id=cid)
    except ValueError as exc:
        raise PermissionError(MSG_CROSS_TENANT) from exc
    if not absolute.is_file():
        raise FileNotFoundError(f"stored attachment missing: {rel}")

    data = absolute.read_bytes()
    filename = str(evidence.get("filename") or absolute.name)
    return store_workflow_template(
        db,
        client_id=cid,
        upload_root=upload_root,
        filename=filename,
        data=data,
        title=title,
        source_slack_file_id=str(evidence.get("file_id") or "") or None,
        created_by_slack_user_id=created_by_slack_user_id,
        content_type=str(evidence.get("mimetype") or "") or None,
        body_text=str(evidence.get("text") or "") or None,
        enqueue_ingest=enqueue_ingest,
        meta={"source": "slack_attachment"},
    )


def copy_template(
    db: Session,
    *,
    client_id: str,
    upload_root: Path,
    template_id: UUID | str,
    owner_slack_user_id: str,
    title: str | None = None,
) -> WorkflowTemplate:
    """
    Copy a shared (or visible) template into a personal draft.

    Does not mutate the original. New file bytes under the tenant root.
    """
    cid_str = require_client_id(client_id)
    owner = (owner_slack_user_id or "").strip()
    if not owner:
        raise ValueError("owner_slack_user_id is required for copy")

    source = get_template(db, client_id=cid_str, template_id=template_id)
    absolute = resolve_stored_path(
        upload_root,
        source.storage_relative_path,
        client_id=cid_str,
    )
    if not absolute.is_file():
        raise FileNotFoundError("source workflow file missing on disk")

    data = absolute.read_bytes()
    stored = store_upload(
        upload_root=upload_root,
        client_id=cid_str,
        file_role=FileRole.WORKFLOW,
        filename=source.original_filename,
        data=data,
    )

    draft_title = (title or f"Copy of {source.title}").strip()[:255]
    row = WorkflowTemplate(
        tenant_id=UUID(cid_str),
        title=draft_title,
        source_slack_file_id=None,
        storage_relative_path=stored.relative_path,
        content_hash=content_hash_bytes(data),
        original_filename=stored.original_filename,
        body_text=source.body_text,
        created_by_slack_user_id=owner,
        created_by_user_id=None,
        owner_slack_user_id=owner,
        visibility=VISIBILITY_PERSONAL,
        parent_id=source.id,
        version=1,
        meta={
            "copied_from": str(source.id),
            "upload_id": stored.upload_id,
            "file_role": str(FileRole.WORKFLOW),
        },
    )
    db.add(row)
    db.flush()
    logger.info(
        "workflow_copied client_id=%s parent=%s draft=%s owner=%s",
        cid_str,
        source.id,
        row.id,
        owner,
    )
    return row


def update_personal_draft(
    db: Session,
    *,
    client_id: str,
    template_id: UUID | str,
    owner_slack_user_id: str,
    title: str | None = None,
    body_text: str | None = None,
) -> WorkflowTemplate:
    """Edit a personal draft; shared originals are immutable via this path."""
    cid_str = require_client_id(client_id)
    owner = (owner_slack_user_id or "").strip()
    row = get_template(db, client_id=cid_str, template_id=template_id)

    if row.visibility != VISIBILITY_PERSONAL:
        raise PermissionError(MSG_FORBIDDEN_EDIT)
    if (row.owner_slack_user_id or "") != owner:
        raise PermissionError(MSG_FORBIDDEN_EDIT)

    if title is not None:
        cleaned = title.strip()
        if cleaned:
            row.title = cleaned[:255]
    if body_text is not None:
        row.body_text = body_text[:50_000] if body_text else None
        row.version = int(row.version or 1) + 1

    db.flush()
    return row


def template_to_dict(row: WorkflowTemplate) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "client_id": str(row.tenant_id),
        "title": row.title,
        "source_slack_file_id": row.source_slack_file_id,
        "storage_relative_path": row.storage_relative_path,
        "content_hash": row.content_hash,
        "original_filename": row.original_filename,
        "body_text_preview": (row.body_text or "")[:500] or None,
        "created_by_slack_user_id": row.created_by_slack_user_id,
        "created_by_user_id": str(row.created_by_user_id) if row.created_by_user_id else None,
        "owner_slack_user_id": row.owner_slack_user_id,
        "visibility": row.visibility,
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "version": row.version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def template_to_evidence(row: WorkflowTemplate) -> dict[str, Any]:
    """Shape a stored template as attached_evidence for advice compose."""
    cid = str(row.tenant_id)
    text = (row.body_text or "").strip()
    return {
        "client_id": cid,
        "file_id": str(row.source_slack_file_id or row.id),
        "filename": row.original_filename,
        "mimetype": None,
        "text": text,
        "stored_relative_path": row.storage_relative_path,
        "unit_count": 1 if text else 0,
        "parse_error": None if text else "empty_body",
        "source": "workflow_template",
        "kind": "workflow_template",
        "title": row.title,
        "label": f"workflow_template:{row.title}",
        "point_id": f"workflow:{row.id}",
        "template_id": str(row.id),
        "score": 1.0,
        "source_format": "workflow_library",
    }


_UUID_IN_TEXT = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I,
)


def extract_template_id_from_text(text: str) -> str | None:
    m = _UUID_IN_TEXT.search(text or "")
    return m.group(1) if m else None


def resolve_template_for_advice(
    db: Session,
    *,
    client_id: str,
    question: str,
    slack_user_id: str | None = None,
) -> WorkflowTemplate | None:
    """
    Resolve a tenant-scoped template for advice.

    Prefer explicit UUID in the question; otherwise the newest shared (or
    personal) match from a light title search is unused here — callers
    typically rely on attachments when no id is given.
    """
    cid = require_client_id(client_id)
    tid = extract_template_id_from_text(question)
    if tid:
        try:
            return get_template(db, client_id=cid, template_id=tid)
        except LookupError:
            return None
    return None
