"""Tenant file listing API — filesystem inventory per tenant."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.blob_store import LocalDiskBlobStore, resolve_blob_store
from api.app.settings import Settings, get_settings
from api.app.tenant_files.listing import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    TenantFileEntry,
    list_tenant_files,
    resolve_tenant_file_path,
)

router = APIRouter(prefix="/tenant-files", tags=["tenant-files"])


class TenantFileItem(BaseModel):
    relative_path: str
    filename: str
    size_bytes: int
    modified_at: str


class TenantFileListResponse(BaseModel):
    client_id: str
    files: list[TenantFileItem]
    truncated: bool = False
    next_cursor: Optional[str] = Field(
        default=None,
        description="Pass as cursor to fetch the next page when truncated",
    )


def _to_item(entry: TenantFileEntry) -> TenantFileItem:
    return TenantFileItem(
        relative_path=entry.relative_path,
        filename=entry.filename,
        size_bytes=entry.size_bytes,
        modified_at=entry.modified_at,
    )


def _require_local_store(settings: Settings) -> LocalDiskBlobStore:
    store = resolve_blob_store(settings=settings)
    if not isinstance(store, LocalDiskBlobStore):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="tenant file listing requires BLOB_STORE=local",
        )
    return store


def _resolve_client_id(principal: AuthPrincipal) -> str:
    return resolve_tenant_for_principal(
        principal,
        None,
        missing_detail="tenant_id required (membership or X-Client-Id)",
    )


def _guess_media_type(path: Path) -> str:
    media_type, _ = mimetypes.guess_type(path.name)
    return media_type or "application/octet-stream"


@router.get("", response_model=TenantFileListResponse)
def get_tenant_files(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
    prefix: Annotated[Optional[str], Query(description="Optional subfolder filter")] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_LIST_LIMIT, description="Max entries returned"),
    ] = DEFAULT_LIST_LIMIT,
    cursor: Annotated[
        Optional[str],
        Query(description="Pagination cursor (last relative_path from prior page)"),
    ] = None,
) -> TenantFileListResponse:
    """List tenant files from disk under the resolved tenant upload root."""
    client_id = _resolve_client_id(principal)
    store = _require_local_store(settings)

    try:
        entries, truncated = list_tenant_files(
            store,
            client_id=client_id,
            prefix=prefix,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    next_cursor = entries[-1].relative_path if truncated and entries else None
    return TenantFileListResponse(
        client_id=client_id,
        files=[_to_item(entry) for entry in entries],
        truncated=truncated,
        next_cursor=next_cursor,
    )


@router.get("/content")
def download_tenant_file(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
    key: Annotated[str, Query(description="Tenant-root-relative file path")],
) -> FileResponse:
    """Download one tenant file by tenant-root-relative path."""
    client_id = _resolve_client_id(principal)
    store = _require_local_store(settings)

    try:
        path = resolve_tenant_file_path(store, client_id=client_id, relative_path=key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return FileResponse(
        path,
        media_type=_guess_media_type(path),
        filename=path.name,
        content_disposition_type="attachment",
    )
