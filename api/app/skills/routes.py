"""Tenant org skills APIs — .md skills + catalog.json tree."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.blob_store import resolve_blob_store
from api.app.settings import Settings, get_settings
from api.app.skills.store import SkillsStore, SkillsStoreError

router = APIRouter(prefix="/skills", tags=["skills"])


class FolderCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_path: str = Field(default="", max_length=1024)


class SkillCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    body: str = Field(default="", max_length=200_000)
    folder_path: str = Field(default="", max_length=1024)
    filename: Optional[str] = Field(default=None, max_length=255)


class SkillUpdateBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    body: Optional[str] = Field(default=None, max_length=200_000)
    dest_folder_path: Optional[str] = Field(default=None, max_length=1024)
    new_filename: Optional[str] = Field(default=None, max_length=255)


class SkillResponse(BaseModel):
    name: str
    description: str
    path: str
    content: str


class CatalogResponse(BaseModel):
    client_id: str
    catalog: dict[str, Any]


class SkillIndexResponse(BaseModel):
    client_id: str
    skills: list[dict[str, str]]


def _require_tenant(principal: AuthPrincipal) -> str:
    return str(
        resolve_tenant_uuid_for_principal(
            principal,
            missing_detail="tenant context required",
        )
    )


def _store(principal: AuthPrincipal, settings: Settings) -> SkillsStore:
    tid = _require_tenant(principal)
    blob = resolve_blob_store(settings=settings)
    return SkillsStore(client_id=tid, blob_store=blob, settings=settings)


def _raise_store_error(exc: SkillsStoreError) -> None:
    if exc.code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if exc.code == "conflict":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/catalog", response_model=CatalogResponse)
def get_catalog_api(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CatalogResponse:
    store = _store(principal, settings)
    return CatalogResponse(client_id=store.client_id, catalog=store.get_catalog())


@router.get("/index", response_model=SkillIndexResponse)
def get_index_api(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SkillIndexResponse:
    store = _store(principal, settings)
    return SkillIndexResponse(client_id=store.client_id, skills=store.list_index())


@router.post("/folders", response_model=CatalogResponse, status_code=status.HTTP_201_CREATED)
def create_folder_api(
    body: FolderCreateBody,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CatalogResponse:
    store = _store(principal, settings)
    try:
        catalog = store.create_folder(name=body.name, parent_path=body.parent_path)
    except SkillsStoreError as exc:
        _raise_store_error(exc)
    return CatalogResponse(client_id=store.client_id, catalog=catalog)


@router.delete("/folders", response_model=CatalogResponse)
def delete_folder_api(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
    folder_path: Annotated[str, Query(min_length=1, max_length=1024)],
    children: Annotated[
        str,
        Query(
            description="What to do with folder children: delete | relocate",
            max_length=32,
        ),
    ] = "delete",
) -> CatalogResponse:
    store = _store(principal, settings)
    try:
        catalog = store.delete_folder(folder_path, mode=children)
    except SkillsStoreError as exc:
        _raise_store_error(exc)
    return CatalogResponse(client_id=store.client_id, catalog=catalog)


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill_api(
    body: SkillCreateBody,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SkillResponse:
    store = _store(principal, settings)
    try:
        record = store.create_skill(
            name=body.name,
            description=body.description,
            body=body.body,
            folder_path=body.folder_path,
            filename=body.filename,
        )
    except SkillsStoreError as exc:
        _raise_store_error(exc)
    return SkillResponse(
        name=record.name,
        description=record.description,
        path=record.path,
        content=record.content,
    )


@router.get("/file", response_model=SkillResponse)
def get_skill_api(
    path: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SkillResponse:
    store = _store(principal, settings)
    try:
        record = store.read_skill(path)
    except SkillsStoreError as exc:
        _raise_store_error(exc)
    return SkillResponse(
        name=record.name,
        description=record.description,
        path=record.path,
        content=record.content,
    )


@router.patch("/file", response_model=SkillResponse)
def update_skill_api(
    path: str,
    body: SkillUpdateBody,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SkillResponse:
    store = _store(principal, settings)
    try:
        record = store.update_skill(
            path=path,
            name=body.name,
            description=body.description,
            body=body.body,
            dest_folder_path=body.dest_folder_path,
            new_filename=body.new_filename,
        )
    except SkillsStoreError as exc:
        _raise_store_error(exc)
    return SkillResponse(
        name=record.name,
        description=record.description,
        path=record.path,
        content=record.content,
    )


@router.delete("/file", response_model=CatalogResponse)
def delete_skill_api(
    path: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CatalogResponse:
    store = _store(principal, settings)
    try:
        catalog = store.delete_skill(path)
    except SkillsStoreError as exc:
        _raise_store_error(exc)
    return CatalogResponse(client_id=store.client_id, catalog=catalog)
