"""Blob-store Strategy — local disk is the first adapter (Sprint 37)."""

from api.app.blob_store.local_adapter import LocalDiskBlobStore
from api.app.blob_store.provider import BlobStore, get_blob_store, resolve_blob_store

__all__ = [
    "BlobStore",
    "LocalDiskBlobStore",
    "get_blob_store",
    "resolve_blob_store",
]
