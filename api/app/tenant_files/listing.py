"""Filesystem inventory for tenant-scoped blob roots (local adapter only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from api.app.blob_store.keys import normalize_blob_key
from api.app.blob_store.local_adapter import LocalDiskBlobStore

DEFAULT_LIST_LIMIT = 500
MAX_LIST_LIMIT = 2000


@dataclass(frozen=True)
class TenantFileEntry:
    relative_path: str
    filename: str
    size_bytes: int
    modified_at: str


def normalize_list_prefix(prefix: str | None) -> str | None:
    """Normalize an optional subfolder prefix under the tenant root."""
    if not prefix or not str(prefix).strip():
        return None
    rel = str(prefix).strip().replace("\\", "/").strip("/")
    if not rel:
        return None
    return normalize_blob_key(rel)


def normalize_tenant_file_key(relative_path: str) -> str:
    """Normalize a tenant-root-relative file key; reject path escape."""
    rel = str(relative_path or "").strip().replace("\\", "/").strip("/")
    if not rel:
        raise ValueError("key is required")
    return normalize_blob_key(rel)


def resolve_tenant_file_path(
    store: LocalDiskBlobStore,
    *,
    client_id: str,
    relative_path: str,
) -> Path:
    """Resolve a tenant-root-relative path to a file under the tenant upload root."""
    cid = str(client_id or "").strip()
    if not cid:
        raise ValueError("client_id is required")

    rel = normalize_tenant_file_key(relative_path)
    tenant_root = (store.root / cid).resolve()
    target = (tenant_root / rel).resolve()
    if not target.is_relative_to(tenant_root):
        raise ValueError("invalid upload path")
    if not target.is_file() or target.is_symlink():
        raise FileNotFoundError(f"tenant file not found: {rel}")
    return target


def _clamp_limit(limit: int) -> int:
    if limit < 1:
        return DEFAULT_LIST_LIMIT
    return min(limit, MAX_LIST_LIMIT)


def list_tenant_files(
    store: LocalDiskBlobStore,
    *,
    client_id: str,
    prefix: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
    cursor: str | None = None,
) -> tuple[list[TenantFileEntry], bool]:
    """
    Recursively list files under ``{upload_root}/{client_id}/``.

    ``relative_path`` is tenant-root-relative (no ``client_id/`` prefix).
    Returns ``(entries, truncated)``.
    """
    cid = str(client_id or "").strip()
    if not cid:
        raise ValueError("client_id is required")

    prefix_norm = normalize_list_prefix(prefix)
    cursor_norm = normalize_list_prefix(cursor) if cursor else None
    cap = _clamp_limit(limit)

    tenant_root = (store.root / cid).resolve()
    if not tenant_root.is_dir():
        return [], False

    collected: list[TenantFileEntry] = []
    for entry in tenant_root.rglob("*"):
        if not entry.is_file() or entry.is_symlink():
            continue
        try:
            resolved = entry.resolve()
            if not resolved.is_relative_to(tenant_root):
                continue
        except OSError:
            continue

        rel = str(entry.relative_to(tenant_root)).replace("\\", "/")
        if prefix_norm and not (rel == prefix_norm or rel.startswith(f"{prefix_norm}/")):
            continue

        try:
            stat = entry.stat()
        except OSError:
            continue

        collected.append(
            TenantFileEntry(
                relative_path=rel,
                filename=entry.name,
                size_bytes=int(stat.st_size),
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            )
        )

    collected.sort(key=lambda item: item.relative_path.lower())
    if cursor_norm:
        collected = [item for item in collected if item.relative_path > cursor_norm]

    truncated = len(collected) > cap
    return collected[:cap], truncated
