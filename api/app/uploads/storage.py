"""Persist uploaded bytes under data/uploads/{client_id}/."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

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
    absolute_path: Path
    size_bytes: int
    content_type: str | None


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
    """Return sanitized filename or raise ValueError."""
    safe = sanitize_filename(filename)
    ext = extension_of(safe)
    allowed = allowed_extensions(file_role)
    if ext not in allowed:
        raise ValueError(
            f"Extension {ext or '(none)'} not allowed for file_role={file_role}; "
            f"allowed: {sorted(allowed)}"
        )
    return safe


def store_upload(
    *,
    upload_root: Path,
    client_id: str,
    file_role: FileRole,
    filename: str,
    data: bytes,
    content_type: str | None = None,
) -> StoredUpload:
    if not client_id or not str(client_id).strip():
        raise ValueError("client_id is required")
    if not data:
        raise ValueError("empty file")

    safe_name = validate_upload_filename(file_role, filename)
    upload_id = str(uuid.uuid4())
    tenant_dir = Path(upload_root) / str(client_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{upload_id}_{safe_name}"
    absolute = tenant_dir / stored_filename
    absolute.write_bytes(data)

    rel = f"{client_id}/{stored_filename}"
    return StoredUpload(
        upload_id=upload_id,
        client_id=str(client_id),
        file_role=file_role,
        original_filename=safe_name,
        stored_filename=stored_filename,
        relative_path=rel,
        absolute_path=absolute,
        size_bytes=len(data),
        content_type=content_type,
    )


def resolve_stored_path(upload_root: Path, relative_path: str) -> Path:
    """Resolve a stored relative path; reject path escape."""
    root = Path(upload_root).resolve()
    target = (root / relative_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("invalid upload path")
    return target
