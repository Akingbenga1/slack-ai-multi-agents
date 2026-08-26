"""Resolve / store files for ``POST /agent/dry-run`` attachments only.

Keeps blob key + optional local absolute path for the planner; does not ingest
to RAG. Used solely by the agent dry-run endpoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from api.app.blob_store import LocalDiskBlobStore, resolve_blob_store
from api.app.blob_store.keys import resolve_local_blob_path
from api.app.settings import Settings, get_settings
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import store_upload


def attachment_from_upload_bytes(
    *,
    client_id: str,
    filename: str,
    data: bytes,
    content_type: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Store bytes via BlobStore (no ingest) and return dry-run attachment dict."""
    stored = store_upload(
        client_id=str(client_id).strip(),
        file_role=FileRole.DOCUMENT,
        filename=filename or "upload.bin",
        data=data,
        content_type=content_type,
        settings=settings or get_settings(),
    )
    return _attachment_dict(
        filename=stored.original_filename,
        upload_id=stored.upload_id,
        storage_relative_path=stored.relative_path,
        local_path=stored.absolute_path,
        content_type=stored.content_type,
    )


def attachment_from_upload_id(
    *,
    client_id: str,
    upload_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Locate an existing tenant blob named ``{upload_id}_*`` under UPLOAD_DIR."""
    cid = str(client_id).strip()
    uid = str(upload_id or "").strip()
    if not uid:
        raise ValueError("upload_id is required")

    cfg = settings or get_settings()
    store = resolve_blob_store(settings=cfg)
    if not isinstance(store, LocalDiskBlobStore):
        raise ValueError(
            "upload_id resolution requires local blob store (BLOB_STORE=local)"
        )

    tenant_dir = (store.root / cid).resolve()
    if not tenant_dir.is_dir():
        raise ValueError(f"no uploads found for tenant {cid}")

    matches = sorted(tenant_dir.glob(f"{uid}_*"))
    matches = [p for p in matches if p.is_file()]
    if not matches:
        raise ValueError(f"upload_id not found: {uid}")
    if len(matches) > 1:
        raise ValueError(f"upload_id is ambiguous: {uid}")

    path = matches[0]
    key = f"{cid}/{path.name}"
    # Validate key stays under tenant root
    resolve_local_blob_path(store.root, key, client_id=cid)
    original = path.name.split("_", 1)[1] if "_" in path.name else path.name
    return _attachment_dict(
        filename=original,
        upload_id=uid,
        storage_relative_path=key,
        local_path=path,
        content_type=None,
    )


def attachment_from_storage_relative_path(
    *,
    client_id: str,
    storage_relative_path: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Resolve an existing blob key to a dry-run attachment dict."""
    cid = str(client_id).strip()
    key = str(storage_relative_path or "").strip().replace("\\", "/")
    if not key:
        raise ValueError("storage_relative_path is required")

    cfg = settings or get_settings()
    store = resolve_blob_store(settings=cfg)
    if not isinstance(store, LocalDiskBlobStore):
        raise ValueError(
            "storage_relative_path resolution requires local blob store"
        )

    path = resolve_local_blob_path(store.root, key, client_id=cid)
    if not path.is_file():
        raise ValueError(f"blob not found: {key}")

    name = path.name
    upload_id = name.split("_", 1)[0] if "_" in name else None
    original = name.split("_", 1)[1] if "_" in name else name
    return _attachment_dict(
        filename=original,
        upload_id=upload_id,
        storage_relative_path=key,
        local_path=path,
        content_type=None,
    )


def _attachment_dict(
    *,
    filename: str,
    upload_id: str | None,
    storage_relative_path: str,
    local_path: Path | None,
    content_type: str | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "filename": filename,
        "storage_relative_path": storage_relative_path,
    }
    if upload_id:
        out["upload_id"] = upload_id
    if content_type:
        out["mimetype"] = content_type
        out["content_type"] = content_type
    if local_path is not None:
        out["local_path"] = str(Path(local_path).resolve())
        out["absolute_path"] = out["local_path"]
    return out
