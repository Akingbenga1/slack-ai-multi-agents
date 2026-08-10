"""Multipart upload API — tenant-scoped knowledge files."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.billing.plans import require_entitlement
from api.app.db.session import get_db
from api.app.governance.budgets import require_budget
from api.app.settings import Settings, get_settings
from api.app.tenant import get_client_id
from api.app.uploads.roles import FileRole
from api.app.uploads.status import get_ingest_job_by_upload_id, list_ingest_jobs
from api.app.uploads.storage import StoredUpload, store_upload
from worker.queues import queue_for_priority
from worker.tasks import enqueue_ingest_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Multipart size guard (bytes); Compose laptop demos stay modest
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class UploadResponse(BaseModel):
    upload_id: str
    client_id: str
    file_role: FileRole
    filename: str
    relative_path: str
    size_bytes: int
    content_type: Optional[str] = None
    status: str = Field(default="stored", description="stored | queued")
    task_id: Optional[str] = Field(default=None, description="Celery task id when queued")
    queue: Optional[str] = None


class IngestJobResponse(BaseModel):
    job_id: str
    client_id: str
    kind: str
    status: str
    upload_id: Optional[str] = None
    filename: Optional[str] = None
    file_role: Optional[str] = None
    celery_task_id: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class IngestJobListResponse(BaseModel):
    client_id: str
    jobs: list[IngestJobResponse]

def _resolve_tenant(
    principal: AuthPrincipal,
    form_tenant_id: Optional[str],
) -> str:
    return resolve_tenant_for_principal(
        principal,
        form_tenant_id,
        missing_detail="tenant_id required (form tenant_id or X-Client-Id)",
    )


@router.get("/jobs", response_model=IngestJobListResponse)
def list_upload_ingest_jobs(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 20,
) -> IngestJobListResponse:
    """Recent ingest_upload jobs for the caller's tenant."""
    _ = principal
    client_id = get_client_id() or principal.tenant_id
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant context required",
        )
    tid = UUID(str(client_id))
    jobs = list_ingest_jobs(db, tid, limit=limit)
    return IngestJobListResponse(
        client_id=str(tid),
        jobs=[IngestJobResponse(**j) for j in jobs],
    )


@router.get("/status/{upload_id}", response_model=IngestJobResponse)
def upload_ingest_status(
    upload_id: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> IngestJobResponse:
    """Status for the latest ingest job for an upload_id (tenant-scoped)."""
    _ = principal
    client_id = get_client_id() or principal.tenant_id
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant context required",
        )
    tid = UUID(str(client_id))
    row = get_ingest_job_by_upload_id(db, tid, upload_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ingest job found for this upload_id",
        )
    return IngestJobResponse(**row)


def _to_response(
    stored: StoredUpload,
    *,
    status_value: str = "stored",
    task_id: str | None = None,
    queue: str | None = None,
) -> UploadResponse:
    return UploadResponse(
        upload_id=stored.upload_id,
        client_id=stored.client_id,
        file_role=stored.file_role,
        filename=stored.original_filename,
        relative_path=stored.relative_path,
        size_bytes=stored.size_bytes,
        content_type=stored.content_type,
        status=status_value,
        task_id=task_id,
        queue=queue,
    )


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_file(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(description="Knowledge file bytes")],
    file_role: Annotated[FileRole, Form(description="document | slack_history")],
    tenant_id: Annotated[
        Optional[str],
        Form(description="Optional tenant override (platform_owner)"),
    ] = None,
    channel: Annotated[
        Optional[str],
        Form(description="Optional Slack channel override for history dumps"),
    ] = None,
    enqueue: Annotated[
        bool,
        Form(description="Enqueue Celery ingest (default true)"),
    ] = True,
    x_client_id: Annotated[Optional[str], Header(alias="X-Client-Id")] = None,
) -> UploadResponse:
    """
    Multipart upload for org knowledge files.

    Requires Bearer JWT. Tenant from membership / ``X-Client-Id`` / form ``tenant_id``.
    By default enqueues parse → chunk → TEI → Qdrant ingest.
    """
    _ = x_client_id
    client_id = _resolve_tenant(principal, tenant_id)
    if enqueue:
        require_entitlement(db, client_id, "ingest")
        require_budget(db, client_id, "jobs", units=1, require_active_plan=True)

    filename = file.filename or "upload.bin"
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {MAX_UPLOAD_BYTES} bytes",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    try:
        stored = store_upload(
            upload_root=settings.upload_dir_path,
            client_id=client_id,
            file_role=file_role,
            filename=filename,
            data=data,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not enqueue:
        return _to_response(stored, status_value="stored")

    async_result = enqueue_ingest_upload(
        client_id=client_id,
        relative_path=stored.relative_path,
        filename=stored.original_filename,
        file_role=stored.file_role,
        upload_id=stored.upload_id,
        channel=(channel or "").strip() or None,
        priority=0,
    )
    return _to_response(
        stored,
        status_value="queued",
        task_id=async_result.id,
        queue=queue_for_priority(0),
    )
