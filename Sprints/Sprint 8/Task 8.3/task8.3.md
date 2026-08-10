# Task 8.3 — Ingest job for uploads

## Steps

- [x] Document unit chunk → TEI → Qdrant pipeline (kind=`document`)
- [x] Unified `ingest_upload` for `document` | `slack_history` stored files
- [x] Celery task + enqueue helper (jobs row + tenant header)
- [x] Wire `POST /uploads` to enqueue ingest (status `queued`)
- [x] Light unit tests (chunk ids + role routing; mock embed/upsert if needed)

## Acceptance criteria

- [x] Uploaded document file is parsed, chunked, embedded, upserted for that tenant
- [x] Uploaded slack_history dump uses Sprint 7 parsers + message ingest
- [x] Missing `client_id` fail-closed (existing helpers)
- [x] Re-ingest same logical units uses deterministic point ids
