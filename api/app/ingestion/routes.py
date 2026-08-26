"""Ingestion management API — sync dry-run path (no Slack / no Celery)."""

from __future__ import annotations

import logging
from typing import Annotated, Any, Optional

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
from api.app.ingest.upload_ingest import ingest_upload
from api.app.logging_config import log_dry_run_activity
from api.app.settings import Settings, get_settings
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import store_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class IngestDryRunResponse(BaseModel):
    """Synchronous ingest result (no Celery, no Slack)."""

    upload_id: str
    client_id: str
    file_role: FileRole
    filename: str
    relative_path: str
    size_bytes: int
    status: str = Field(default="ingested", description="ingested")
    unit_or_message_count: int
    chunk_count: int
    point_count: int
    point_ids: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)


def _resolve_tenant(
    principal: AuthPrincipal,
    form_tenant_id: Optional[str],
) -> str:
    return resolve_tenant_for_principal(
        principal,
        form_tenant_id,
        missing_detail="tenant_id required (form tenant_id or X-Client-Id)",
    )


@router.post("/dry-run", response_model=IngestDryRunResponse)
async def ingestion_dry_run(
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
    x_client_id: Annotated[Optional[str], Header(alias="X-Client-Id")] = None,
) -> IngestDryRunResponse:
    """
    Store a knowledge file and run ``ingest_upload`` in-process.

    Isolates the upload → parse → chunk → TEI → Qdrant path: no Celery queue
    and no Slack sync/reply pipeline. Requires ``ingest`` entitlement.
    """
    _ = x_client_id
    client_id = _resolve_tenant(principal, tenant_id)
    require_entitlement(db, client_id, "ingest")
    require_budget(db, client_id, "jobs", units=1, require_active_plan=True)

    filename = file.filename or "upload.bin"
    request_meta = {
        "filename": filename,
        "file_role": str(file_role),
        "content_type": file.content_type,
        "channel": (channel or "").strip() or None,
        "tenant_id": tenant_id,
    }
    log_dry_run_activity(
        endpoint="POST /ingestion/dry-run",
        phase="request",
        client_id=client_id,
        request=request_meta,
        celery=None,
    )
    data = await file.read()
    request_meta["size_bytes"] = len(data)
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
            client_id=client_id,
            file_role=file_role,
            filename=filename,
            data=data,
            content_type=file.content_type,
            settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        ingest_result = ingest_upload(
            client_id=client_id,
            file_role=stored.file_role,
            relative_path=stored.relative_path,
            filename=stored.original_filename,
            channel=(channel or "").strip() or None,
            settings=settings,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "ingestion_dry_run_failed client_id=%s upload_id=%s",
            client_id,
            stored.upload_id,
        )
        log_dry_run_activity(
            endpoint="POST /ingestion/dry-run",
            phase="error",
            client_id=client_id,
            request=request_meta,
            error={
                "status_code": 502,
                "detail": "ingest_failed",
                "upload_id": stored.upload_id,
                "exc": str(exc),
            },
            celery=None,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ingest_failed",
        ) from exc

    payload = ingest_result.as_dict()
    response = IngestDryRunResponse(
        upload_id=stored.upload_id,
        client_id=stored.client_id,
        file_role=stored.file_role,
        filename=stored.original_filename,
        relative_path=stored.relative_path,
        size_bytes=stored.size_bytes,
        status="ingested",
        unit_or_message_count=ingest_result.unit_or_message_count,
        chunk_count=ingest_result.chunk_count,
        point_count=len(ingest_result.point_ids),
        point_ids=list(payload.get("point_ids") or []),
        result=payload,
    )
    log_dry_run_activity(
        endpoint="POST /ingestion/dry-run",
        phase="response",
        client_id=client_id,
        request=request_meta,
        response=response.model_dump(),
        celery=None,
    )
    return response
