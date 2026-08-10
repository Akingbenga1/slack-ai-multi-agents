# Task 8.3 journal

## Status

`completed`

## Summary

Document chunk/ingest pipeline (`kind=document`, uuid5 point ids). Unified `ingest_upload` routes `document` vs `slack_history`. Celery `worker.ingest_upload` persists a `jobs` row and runs parse → chunk → TEI → Qdrant. `POST /uploads` enqueues by default (`status=queued`, `task_id`).

## Acceptance criteria checklist

- [x] Document path ingest — done (`ingest_extracted_document` / Celery)
- [x] slack_history reuses Sprint 7 parsers — done
- [x] client_id fail-closed — done (Qdrant helpers)
- [x] Deterministic point ids — done (filename+locator+chunk_index)

## Decision log

- Document points keyed by filename+locator (not upload_id) so same file content path stays idempotent across re-uploads of the same name.
- Optional form `enqueue=false` for store-only; `channel=` for history dumps missing channel.
- Job kind `ingest_upload`.

## Needs human

None for this task. Full live “upload PDF → search chunk” still needs Compose TEI/Qdrant + Celery worker running (operator smoke).

## Files changed

- `api/app/ingest/document_chunk.py`, `document_pipeline.py`, `upload_ingest.py`
- `worker/tasks.py`, `worker/job_meta.py`
- `api/app/uploads/routes.py`
- `tests/ingest/test_upload_ingest.py`, `tests/uploads/test_upload_api.py`
- `docs/document-ingest.md`, `docs/uploads.md`, `docs/celery.md`, `README.md`

## Resume notes

Batch 8.1–8.3 done. Next: **Continue Sprint 8 from Task 8.4** (minimal org UI upload widget).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/uploads tests/ingest -q  → 36 passed
```
