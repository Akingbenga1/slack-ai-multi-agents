"""Filesystem listing unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.blob_store import LocalDiskBlobStore
from api.app.settings import Settings
from api.app.tenant_files.listing import list_tenant_files


def test_list_tenant_files_skips_symlinks(tmp_path: Path):
    cid = "11111111-1111-1111-1111-111111111111"
    tenant_dir = tmp_path / cid
    tenant_dir.mkdir()
    real = tenant_dir / "real.txt"
    real.write_text("ok", encoding="utf-8")
    link = tenant_dir / "link.txt"
    link.symlink_to(real)

    store = LocalDiskBlobStore(Settings(upload_dir=str(tmp_path)), root=tmp_path)
    entries, truncated = list_tenant_files(store, client_id=cid)
    paths = {item.relative_path for item in entries}
    assert paths == {"real.txt"}
    assert truncated is False
