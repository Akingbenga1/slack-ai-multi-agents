"""Product upload helpers — persist via ``BlobStore`` (Sprint 37).

``relative_path`` values are **blob keys** (tenant-scoped), not absolute
filesystem paths. The local adapter maps keys under ``UPLOAD_DIR``.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from api.app.blob_store import LocalDiskBlobStore, resolve_blob_store
from api.app.blob_store.keys import normalize_blob_key, resolve_local_blob_path
from api.app.blob_store.provider import BlobStore
from api.app.settings import Settings
from api.app.uploads.roles import FileRole, allowed_extensions

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StoredUpload:
    upload_id: str
    client_id: str
    file_role: FileRole
    original_filename: str
    stored_filename: str
    relative_path: str
    size_bytes: int
    content_type: str | None
    # Local-adapter convenience only; None when the store is not on-disk.
    absolute_path: Path | None = None


def sanitize_filename(name: str) -> str:
    base = Path(name).name.strip() or "upload.bin"
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "upload.bin"
    # Cap length while keeping extension when possible
    if len(cleaned) > 180:
        suffix = Path(cleaned).suffix[:20]
        cleaned = cleaned[: 180 - len(suffix)] + suffix
    return cleaned


def extension_of(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_upload_filename(file_role: FileRole, filename: str) -> str:
    """Return sanitized filename or raise ValueError.

    Sanitization always applies; the extension allowlist applies only to roles
    that declare one (see ``allowed_extensions``).
    """
    safe = sanitize_filename(filename)
    allowed = allowed_extensions(file_role)
    if allowed is None:
        return safe
    ext = extension_of(safe)
    if ext not in allowed:
        raise ValueError(
            f"Extension {ext or '(none)'} not allowed for file_role={file_role}; "
            f"allowed: {sorted(allowed)}"
        )
    return safe


def store_upload(
    *,
    client_id: str,
    file_role: FileRole,
    filename: str,
    data: bytes,
    content_type: str | None = None,
    upload_root: Path | None = None,
    blob_store: BlobStore | None = None,
    settings: Settings | None = None,
) -> StoredUpload:
    if not client_id or not str(client_id).strip():
        raise ValueError("client_id is required")
    if not data:
        raise ValueError("empty file")

    safe_name = validate_upload_filename(file_role, filename)
    upload_id = str(uuid.uuid4())
    cid = str(client_id).strip()
    stored_filename = f"{upload_id}_{safe_name}"
    key = f"{cid}/{stored_filename}"

    store = resolve_blob_store(
        settings=settings,
        upload_root=upload_root,
        blob_store=blob_store,
    )
    canonical = store.put(client_id=cid, key=key, data=data)

    absolute: Path | None = None
    if isinstance(store, LocalDiskBlobStore):
        absolute = resolve_local_blob_path(store.root, canonical, client_id=cid)

    return StoredUpload(
        upload_id=upload_id,
        client_id=cid,
        file_role=file_role,
        original_filename=safe_name,
        stored_filename=stored_filename,
        relative_path=canonical,
        size_bytes=len(data),
        content_type=content_type,
        absolute_path=absolute,
    )


def normalize_relative_path(relative_path: str) -> str:
    """Normalize blob key; reject absolute / ``..`` segments (fail-closed)."""
    return normalize_blob_key(relative_path)


def resolve_stored_path(
    upload_root: Path,
    relative_path: str,
    *,
    client_id: str | None = None,
) -> Path:
    """
    Resolve a blob key under a local root (legacy helper).

    Prefer ``BlobStore.resolve`` / ``get`` in product code; kept for the local
    adapter bridge and path-isolation tests.
    """
    return resolve_local_blob_path(
        upload_root, relative_path, client_id=client_id
    )
