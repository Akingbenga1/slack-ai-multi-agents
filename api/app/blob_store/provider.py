"""Blob-store Strategy + Factory (Sprint 37).

Tenant file I/O knows only ``BlobStore`` — put / get / rename / resolve with
fail-closed ``client_id``. Local disk (and later S3 / MinIO) live in adapters;
``get_blob_store`` selects by ``BLOB_STORE``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from api.app.settings import Settings, get_settings

if TYPE_CHECKING:
    from pathlib import Path


class BlobStore(Protocol):
    """Vendor-neutral tenant-scoped blob store.

    Keys are opaque strings (e.g. ``{client_id}/{upload_id}_{filename}``) —
    the same values stored as ``relative_path`` / ``storage_relative_path``.
    Adapters must not require callers to know a filesystem path.
    """

    @property
    def name(self) -> str:
        """Adapter id (e.g. ``local``)."""
        ...

    def put(
        self,
        *,
        client_id: str | None,
        key: str,
        data: bytes,
    ) -> str:
        """Store ``data`` at ``key`` under the tenant. Returns canonical key."""
        ...

    def get(
        self,
        *,
        client_id: str | None,
        key: str,
    ) -> bytes:
        """Load bytes for ``key``. Fail-closed on missing / wrong tenant."""
        ...

    def rename(
        self,
        *,
        client_id: str | None,
        key: str,
        new_key: str,
    ) -> str:
        """Move ``key`` → ``new_key`` under the tenant. Returns canonical new key."""
        ...

    def resolve(
        self,
        *,
        client_id: str | None,
        key: str,
    ) -> str:
        """Normalize and validate ``key`` under the tenant; return canonical key."""
        ...

    def delete(
        self,
        *,
        client_id: str | None,
        key: str,
    ) -> None:
        """Remove ``key`` under the tenant. Missing keys are a no-op."""
        ...


def get_blob_store(settings: Settings | None = None) -> BlobStore:
    """Factory: select blob adapter by ``BLOB_STORE`` (default ``local``)."""
    settings = settings or get_settings()
    name = (settings.blob_store or "local").strip().lower()
    if name == "local":
        from api.app.blob_store.local_adapter import LocalDiskBlobStore

        return LocalDiskBlobStore(settings)
    if name == "s3":
        raise ValueError(
            "s3 blob-store adapter is not implemented — set BLOB_STORE=local "
            "(documented extension only)"
        )
    raise ValueError(f"Unknown BLOB_STORE={name!r}; expected local|s3")


def resolve_blob_store(
    *,
    settings: Settings | None = None,
    upload_root: "Path | None" = None,
    blob_store: BlobStore | None = None,
) -> BlobStore:
    """
    Resolve a ``BlobStore`` for product call sites.

    Prefer an explicit ``blob_store``. ``upload_root`` forces the local adapter
    with that root (tests / callers that still pass a temp dir). Otherwise use
    the ``BLOB_STORE`` factory.
    """
    if blob_store is not None:
        return blob_store
    if upload_root is not None:
        from pathlib import Path

        from api.app.blob_store.local_adapter import LocalDiskBlobStore

        return LocalDiskBlobStore(settings or get_settings(), root=Path(upload_root))
    return get_blob_store(settings)
