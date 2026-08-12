# Task 37.4 journal

## Status

`completed`

## Summary

Locked Sprint 37 exit with fail-closed + isolation regression: product upload/PDF/rename paths stay on `BlobStore` / `PdfRenderer`; `fpdf` and filesystem blob I/O stay in adapters. Moved default PDF wiring to `default_pdf_renderer()` so the product facade no longer names `Fpdf2PdfRenderer`. Demo default remains `BLOB_STORE=local` + fpdf2. `review.md` gaps already Implemented.

## Acceptance criteria checklist

- [x] Fail-closed `client_id` on store/load/rename
- [x] Existing upload + PDF/rename smokes still pass
- [x] Sprint 37 exit met: File I/O and PDF export do not import local paths or fpdf2 outside their adapters

## Decision log

- **`default_pdf_renderer()`:** composition root only (no `PDF_RENDERER` env). Keeps the single-renderer “no Factory” rule while product code talks `PdfRenderer` only.
- **Isolation scan:** mirrors Sprint 35.4 — AST forbid `fpdf` imports on PDF product modules; forbid `write_bytes` / `read_bytes` / `Path.rename` on blob product modules; require BlobStore references.

## Needs human

None new.

## Files changed

- `api/app/pdf_renderer/provider.py`, `__init__.py` (`default_pdf_renderer`)
- `api/app/slack/pdf_export.py`
- `tests/blob_store/test_blob_pdf_isolation.py` (new)
- `Sprints/Sprint 37/Task 37.4/task37.4.md`

## Smoke test results

- `uv run pytest tests/blob_store/ tests/pdf_renderer/ tests/uploads/ tests/slack/test_pdf_export.py tests/slack/test_file_rename.py tests/ingest/test_upload_ingest.py tests/slack/test_attachments.py tests/workflows/test_library.py -q` → **53 passed**

## Resume notes

**Sprint 37 complete.** Next Ralph batch: **Continue Sprint 38 from Task 38.1** — `JobQueue` + Celery adapter.

## Open questions

None.
