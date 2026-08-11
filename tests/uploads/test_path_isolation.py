"""Regression: upload path isolation + tenant resolve fail-closed."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from api.app.tenant import clear_client_id, set_client_id
from api.app.uploads.storage import resolve_stored_path, store_upload
from api.app.uploads.roles import FileRole
from worker.tenant_job import resolve_tenant_id


def test_resolve_stored_path_rejects_dotdot_cross_tenant(tmp_path: Path):
    victim = str(uuid4())
    attacker = str(uuid4())
    stored = store_upload(
        upload_root=tmp_path,
        client_id=victim,
        file_role=FileRole.DOCUMENT,
        filename="secret.csv",
        data=b"top-secret",
    )
    # Classic bypass: prefix check alone would allow {attacker}/../{victim}/file
    evil = f"{attacker}/../{stored.relative_path}"
    with pytest.raises(ValueError, match="invalid upload path"):
        resolve_stored_path(tmp_path, evil, client_id=attacker)
    # Sibling-root startswith bypass (uploads vs uploads_evil) still blocked
    root = tmp_path.resolve()
    evil_sibling = root.parent / f"{root.name}_evil" / "x.bin"
    evil_sibling.parent.mkdir(parents=True, exist_ok=True)
    evil_sibling.write_bytes(b"nope")
    with pytest.raises(ValueError):
        resolve_stored_path(tmp_path, f"../{root.name}_evil/x.bin")


def test_resolve_stored_path_ok_under_tenant(tmp_path: Path):
    cid = str(uuid4())
    stored = store_upload(
        upload_root=tmp_path,
        client_id=cid,
        file_role=FileRole.DOCUMENT,
        filename="ok.csv",
        data=b"hello",
    )
    path = resolve_stored_path(tmp_path, stored.relative_path, client_id=cid)
    assert path.is_file()
    assert path.read_bytes() == b"hello"


def test_resolve_tenant_id_fail_closed(monkeypatch: pytest.MonkeyPatch):
    clear_client_id()
    with pytest.raises(ValueError, match="tenant_id required"):
        resolve_tenant_id(None)


def test_resolve_tenant_id_header_kwarg_mismatch():
    a, b = str(uuid4()), str(uuid4())
    set_client_id(a)
    try:
        with pytest.raises(ValueError, match="mismatch"):
            resolve_tenant_id(b)
    finally:
        clear_client_id()
