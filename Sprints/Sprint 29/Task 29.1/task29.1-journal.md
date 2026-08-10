# Task 29.1 journal

## Status

`completed`

## Summary

Extracted shared `ingest_chunks` (TEI batch + Qdrant upsert) into `api/app/ingest/chunks_ingest.py`. Slack `ingest_messages` and document `ingest_document_units` are thin wrappers that pass Strategy hooks for point id / payload. `DEFAULT_EMBED_BATCH` is single-sourced.

## Acceptance criteria checklist

- [x] Shared TEI batch + upsert
- [x] Strategy hooks for point id / payload
- [x] Thin Slack vs document wrappers
- [x] Existing ingest tests green

## Decision log

- **Template Method + Strategy (function-level):** same shape as Sprint 27 `run_grounded_draft` — one skeleton, injectable `point_id_fn` / `payload_fn`; no AbstractClass hierarchy.
- Kept `point_id_for_*` / payload helpers in pipeline modules so existing imports/tests stay stable.

## Needs human

(none)

## Files changed

- `api/app/ingest/chunks_ingest.py` (new)
- `api/app/ingest/pipeline.py`
- `api/app/ingest/document_pipeline.py`
- `api/app/ingest/__init__.py`
- `tests/ingest/test_chunks_ingest.py` (new)
- `Sprints/Sprint 29/Task 29.1/task29.1.md`

## Resume notes

Continue batch with Task 29.2 (`@tenant_job`).

## Open questions

(none)

## Smoke test results

- ingest unit suite green (incl. new `test_chunks_ingest`)
