"""BlobStore factory + local adapter smoke (Sprint 37.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from api.app.blob_store import LocalDiskBlobStore, get_blob_store
from api.app.settings import Settings


def test_factory_defaults_to_local(tmp_path: Path):
    store = get_blob_store(Settings(blob_store="local", upload_dir=str(tmp_path)))
    assert isinstance(store, LocalDiskBlobStore)
    assert store.name == "local"


def test_factory_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown BLOB_STORE"):
        get_blob_store(Settings(blob_store="gcs"))


def test_factory_s3_not_implemented():
    with pytest.raises(ValueError, match="s3"):
        get_blob_store(Settings(blob_store="s3"))


def test_local_put_get_rename_roundtrip(tmp_path: Path):
    cid = str(uuid4())
    store = LocalDiskBlobStore(Settings(upload_dir=str(tmp_path)), root=tmp_path)
    key = f"{cid}/u1_report.csv"
    assert store.put(client_id=cid, key=key, data=b"hello") == key
    assert store.get(client_id=cid, key=key) == b"hello"

    new_key = f"{cid}/u1_renamed.csv"
    assert store.rename(client_id=cid, key=key, new_key=new_key) == new_key
    assert store.get(client_id=cid, key=new_key) == b"hello"
    with pytest.raises(FileNotFoundError):
        store.get(client_id=cid, key=key)


def test_local_missing_client_id_raises(tmp_path: Path):
    store = LocalDiskBlobStore(root=tmp_path)
    with pytest.raises(ValueError, match="client_id is required"):
        store.put(client_id=None, key="x/a.bin", data=b"x")
    with pytest.raises(ValueError, match="client_id is required"):
        store.get(client_id="", key="x/a.bin")
    with pytest.raises(ValueError, match="client_id is required"):
        store.resolve(client_id="  ", key="x/a.bin")
    with pytest.raises(ValueError, match="client_id is required"):
        store.rename(client_id=None, key="x/a.bin", new_key="x/b.bin")


def test_local_rejects_cross_tenant_key(tmp_path: Path):
    victim = str(uuid4())
    attacker = str(uuid4())
    store = LocalDiskBlobStore(root=tmp_path)
    key = f"{victim}/secret.csv"
    store.put(client_id=victim, key=key, data=b"top-secret")

    with pytest.raises(ValueError, match="not under this tenant"):
        store.get(client_id=attacker, key=key)
    with pytest.raises(ValueError, match="invalid upload path"):
        store.resolve(client_id=attacker, key=f"{attacker}/../{key}")
