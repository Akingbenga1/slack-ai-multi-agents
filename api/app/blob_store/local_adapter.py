"""Local-disk Adapter for ``BlobStore`` (Sprint 37).

Owns filesystem paths under ``UPLOAD_DIR`` / ``{client_id}/``. Product code
talks in blob keys only; this adapter maps keys ↔ paths with fail-closed
tenant isolation.
"""

from __future__ import annotations

from pathlib import Path

from api.app.blob_store.keys import normalize_blob_key, resolve_local_blob_path
from api.app.settings import Settings, get_settings


class LocalDiskBlobStore:
    """Local disk put / get / rename / resolve under ``UPLOAD_DIR``."""

    name = "local"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        root: Path | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._root = Path(root) if root is not None else self.settings.upload_dir_path

    @property
    def root(self) -> Path:
        """Local-adapter root (``UPLOAD_DIR``). Adapter-only — not a product API."""
        return self._root

    def put(
        self,
        *,
        client_id: str | None,
        key: str,
        data: bytes,
    ) -> str:
        cid = _require_client_id(client_id)
        if not data:
            raise ValueError("empty file")
        canonical = self.resolve(client_id=cid, key=key)
        path = resolve_local_blob_path(self.root, canonical, client_id=cid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return canonical

    def get(
        self,
        *,
        client_id: str | None,
        key: str,
    ) -> bytes:
        cid = _require_client_id(client_id)
        canonical = self.resolve(client_id=cid, key=key)
        path = resolve_local_blob_path(self.root, canonical, client_id=cid)
        if not path.is_file():
            raise FileNotFoundError(f"blob not found: {canonical}")
        return path.read_bytes()

    def rename(
        self,
        *,
        client_id: str | None,
        key: str,
        new_key: str,
    ) -> str:
        cid = _require_client_id(client_id)
        src_key = self.resolve(client_id=cid, key=key)
        dest_key = self.resolve(client_id=cid, key=new_key)
        src = resolve_local_blob_path(self.root, src_key, client_id=cid)
        dest = resolve_local_blob_path(self.root, dest_key, client_id=cid)
        if not src.is_file():
            raise FileNotFoundError(f"blob not found: {src_key}")
        if src.resolve() == dest.resolve():
            return dest_key
        if dest.exists():
            raise FileExistsError(f"target already exists: {dest_key}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
        return dest_key

    def resolve(
        self,
        *,
        client_id: str | None,
        key: str,
    ) -> str:
        cid = _require_client_id(client_id)
        rel = normalize_blob_key(key)
        if rel != cid and not rel.startswith(f"{cid}/"):
            raise ValueError("stored path is not under this tenant")
        # Resolve through path helpers so ``..`` / sibling-root escapes fail closed.
        resolve_local_blob_path(self.root, rel, client_id=cid)
        return rel


def _require_client_id(client_id: str | None) -> str:
    cid = str(client_id or "").strip()
    if not cid:
        raise ValueError("client_id is required")
    return cid
