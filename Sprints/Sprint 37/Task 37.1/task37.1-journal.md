# Task 37.1 journal

## Status

`completed`

## Summary

Introduced `BlobStore` Strategy + `get_blob_store` Factory and `LocalDiskBlobStore` Adapter. Keys are tenant-scoped blob ids (same shape as `relative_path` / `storage_relative_path`). Local disk under `UPLOAD_DIR` is the first adapter; `BLOB_STORE=s3` is a documented stub. Product upload/rename/library call sites still use legacy helpers until Task 37.2.

## Acceptance criteria checklist

- [x] Product file I/O can talk to a `BlobStore`; local disk is one adapter
- [x] put / get / rename / resolve are on the interface with mandatory `client_id`
- [x] `BLOB_STORE=local|s3` selects the adapter (s3 may raise not-implemented)

## Decision log

- **Patterns:** Strategy (`BlobStore`) + Factory (`get_blob_store`) + Adapter (`LocalDiskBlobStore`).
- **Blob keys** = existing relative paths (`{client_id}/{upload_id}_{filename}`); no column rename.
- **Path isolation** reused via `normalize_relative_path` / `resolve_stored_path` inside the local adapter (same fail-closed rules as Sprint 8/23).
- **`UPLOAD_DIR` kept** as local-adapter root; no S3 credential env this sprint.
- **s3** raises not-implemented (documented stub only).

## Needs human

None new.

## Files changed

- `api/app/blob_store/` (`provider.py`, `local_adapter.py`, `__init__.py`)
- `api/app/settings.py` (`blob_store`)
- `.env.example` (`BLOB_STORE`)
- `docs/uploads.md`
- `tests/blob_store/test_blob_store_factory.py`
- `Sprints/Sprint 37/Task 37.1/task37.1.md`

## Resume notes

Done. Continue Task 37.2 — wire upload / intake / rename / library / ingest through `BlobStore`.

## Open questions

None.

## Smoke test results

`uv run pytest tests/blob_store/test_blob_store_factory.py -q` → 6 passed.
