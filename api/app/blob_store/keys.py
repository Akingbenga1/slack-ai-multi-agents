"""Blob-key normalization + local-path resolve helpers (Sprint 37).

Keys are opaque tenant-scoped strings. The local adapter maps them under a
filesystem root with the same fail-closed rules as Sprint 8 uploads.
"""

from __future__ import annotations

from pathlib import Path


def normalize_blob_key(key: str) -> str:
    """Normalize and reject absolute / ``..`` segments (fail-closed)."""
    rel = (key or "").replace("\\", "/").strip()
    if not rel or rel.startswith("/"):
        raise ValueError("invalid upload path")
    parts = Path(rel).parts
    if ".." in parts or any(p in ("", ".") for p in parts):
        raise ValueError("invalid upload path")
    return "/".join(parts)


def resolve_local_blob_path(
    upload_root: Path,
    key: str,
    *,
    client_id: str | None = None,
) -> Path:
    """
    Map a blob key to a path under ``upload_root``; reject path escape.

    When ``client_id`` is set, require the key under that tenant prefix.
    Uses ``Path.is_relative_to`` so sibling roots cannot bypass the check.
    """
    root = Path(upload_root).resolve()
    rel = normalize_blob_key(key)
    if client_id is not None:
        cid = str(client_id).strip()
        if not cid:
            raise ValueError("client_id is required")
        if rel != cid and not rel.startswith(f"{cid}/"):
            raise ValueError("stored path is not under this tenant")
        tenant_root = (root / cid).resolve()
        target = (root / rel).resolve()
        if not target.is_relative_to(tenant_root):
            raise ValueError("invalid upload path")
        return target

    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise ValueError("invalid upload path")
    return target
