# Task 37.2 journal

## Status

`completed`

## Summary

Wired portal uploads, Slack intake (incl. raw fallback), org-copy rename, workflow library load/copy, and upload ingest through `BlobStore`. Call sites use blob keys + put/get/rename; local filesystem paths stay inside the local adapter.

## Acceptance criteria checklist

- [x] Org copies, portal uploads, Slack intake, rename, workflow library store/load use `BlobStore`
- [x] Those modules do not assume a local filesystem path

## Decision log

- **`resolve_blob_store`** accepts optional `upload_root` so existing tests/callers that pass a temp dir still force the local adapter without rewriting every signature to inject a store.
- **`store_upload`** builds the blob key then `put`; `absolute_path` is optional (set only for `LocalDiskBlobStore`).
- **Ingest** loads bytes via `get_blob_store(settings).get` and feeds parsers with bytes / `BytesIO` (no `Path` open).
- Path helpers live in `blob_store/keys.py` to avoid circular imports with `uploads.storage`.

## Needs human

None new.

## Files changed

- `api/app/blob_store/keys.py`, `provider.py` (`resolve_blob_store`), `local_adapter.py`, `__init__.py`
- `api/app/uploads/storage.py`, `routes.py`
- `api/app/slack/files/intake.py`, `rename.py`
- `api/app/workflows/library.py`
- `api/app/ingest/upload_ingest.py`
- `docs/uploads.md`, `docs/workflow-library.md`, `docs/slack-file-actions.md`

## Resume notes

Done. Continue Task 37.3 — `PdfRenderer` + fpdf2 adapter.

## Open questions

None.

## Smoke test results

`uv run pytest tests/blob_store/ tests/uploads/ tests/ingest/test_upload_ingest.py tests/slack/test_file_rename.py tests/slack/test_attachments.py tests/workflows/test_library.py -q` → 39 passed.
