"""Org portal API — shared workflow library (Sprint 24.3)."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.db.session import get_db
from api.app.settings import Settings, get_settings
from api.app.uploads.routes import MAX_UPLOAD_BYTES
from api.app.workflows.library import (
    MSG_FORBIDDEN_EDIT,
    MSG_NOT_FOUND,
    copy_template,
    get_template,
    list_templates,
    store_workflow_template,
    template_to_dict,
    update_personal_draft,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowTemplateResponse(BaseModel):
    id: str
    client_id: str
    title: str
    source_slack_file_id: Optional[str] = None
    storage_relative_path: str
    content_hash: str
    original_filename: str
    body_text_preview: Optional[str] = None
    created_by_slack_user_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    owner_slack_user_id: Optional[str] = None
    visibility: str
    parent_id: Optional[str] = None
    version: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkflowListResponse(BaseModel):
    client_id: str
    templates: list[WorkflowTemplateResponse]


class CopyRequest(BaseModel):
    owner_slack_user_id: str = Field(
        ...,
        min_length=1,
        description="Slack user id that will own the personal draft",
    )
    title: Optional[str] = None


class EditDraftRequest(BaseModel):
    owner_slack_user_id: str = Field(..., min_length=1)
    title: Optional[str] = None
    body_text: Optional[str] = None


class WorkflowUploadResponse(WorkflowTemplateResponse):
    created: bool = Field(
        description="False when an existing shared template matched (idempotent)."
    )
    ingested_queued: bool = False
    ingest_task_id: Optional[str] = None


def _resolve_tenant(principal: AuthPrincipal) -> str:
    return resolve_tenant_for_principal(
        principal,
        missing_detail="tenant_id required (X-Client-Id)",
    )


@router.get("", response_model=WorkflowListResponse)
def list_workflow_templates(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[Optional[str], Query(description="Search title/filename/body")] = None,
    include_personal_for: Annotated[
        Optional[str],
        Query(description="Also include this Slack user's personal drafts"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> WorkflowListResponse:
    client_id = _resolve_tenant(principal)
    rows = list_templates(
        db,
        client_id=client_id,
        q=q,
        include_personal_for=include_personal_for,
        limit=limit,
    )
    return WorkflowListResponse(
        client_id=client_id,
        templates=[WorkflowTemplateResponse(**template_to_dict(r)) for r in rows],
    )


@router.post("/upload", response_model=WorkflowUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_workflow_template(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="Workflow file (PDF, DOCX, XLSX, CSV, MD, TXT)")],
    title: Annotated[
        Optional[str],
        Form(description="Optional title override; defaults from filename"),
    ] = None,
    enqueue_ingest: Annotated[
        bool,
        Form(description="Enqueue Qdrant ingest for document-parseable types (default false)"),
    ] = False,
) -> WorkflowUploadResponse:
    """
    Store a shared workflow template for the caller's organisation.

    Persists to ``workflow_templates`` via the library store path (same as Slack
    store). Does not run the agent. ``enqueue_ingest`` is off by default.
    """
    client_id = _resolve_tenant(principal)
    filename = file.filename or "workflow.bin"
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
        result = store_workflow_template(
            db,
            client_id=client_id,
            upload_root=settings.upload_dir_path,
            filename=filename,
            data=data,
            title=(title or "").strip() or None,
            content_type=file.content_type,
            enqueue_ingest=enqueue_ingest,
            meta={"source": "api_upload"},
        )
        payload = template_to_dict(result.template)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)[:300],
        ) from exc

    return WorkflowUploadResponse(
        **payload,
        created=result.created,
        ingested_queued=result.ingested_queued,
        ingest_task_id=result.task_id,
    )


@router.get("/{template_id}", response_model=WorkflowTemplateResponse)
def get_workflow_template(
    template_id: UUID,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkflowTemplateResponse:
    client_id = _resolve_tenant(principal)
    try:
        row = get_template(db, client_id=client_id, template_id=template_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or MSG_NOT_FOUND,
        ) from exc
    return WorkflowTemplateResponse(**template_to_dict(row))


@router.post("/{template_id}/copy", response_model=WorkflowTemplateResponse)
def copy_workflow_template(
    template_id: UUID,
    body: CopyRequest,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkflowTemplateResponse:
    client_id = _resolve_tenant(principal)
    try:
        row = copy_template(
            db,
            client_id=client_id,
            upload_root=settings.upload_dir_path,
            template_id=template_id,
            owner_slack_user_id=body.owner_slack_user_id,
            title=body.title,
        )
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)[:300],
        ) from exc
    return WorkflowTemplateResponse(**template_to_dict(row))


@router.patch("/{template_id}", response_model=WorkflowTemplateResponse)
def edit_workflow_draft(
    template_id: UUID,
    body: EditDraftRequest,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkflowTemplateResponse:
    client_id = _resolve_tenant(principal)
    try:
        row = update_personal_draft(
            db,
            client_id=client_id,
            template_id=template_id,
            owner_slack_user_id=body.owner_slack_user_id,
            title=body.title,
            body_text=body.body_text,
        )
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc) or MSG_FORBIDDEN_EDIT,
        ) from exc
    return WorkflowTemplateResponse(**template_to_dict(row))
