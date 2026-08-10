# Task 19.2 journal

## Status

`completed`

## Summary

Added ingest job status APIs and `/app/knowledge` with upload, ingest table, and Slack sync status/trigger. Home portal now links to knowledge instead of embedding the raw widget.

## Acceptance criteria checklist

- [x] Upload from portal
- [x] Ingest + sync status / trigger
- [x] Cross-tenant denied

## Decision log

- Status from `jobs` rows (`kind=ingest_upload`), matched by `payload.upload_id`.
- Upload widget uses `X-Client-Id` from session only (no form `tenant_id`).

## Needs human

Live verify with worker running: upload → job row → status refresh; Slack sync needs install.

## Files changed

- `api/app/uploads/status.py`, `routes.py`
- `web/app/app/knowledge/page.tsx`, `components/{KnowledgePanel,IngestJobsPanel,SyncStatusPanel,UploadWidget}.tsx`
- `tests/uploads/test_ingest_status.py`
- `docs/uploads.md`, `docs/portal.md`
- `Sprints/Sprint 19/Task 19.2/*`

## Resume notes

Next in batch: **Task 19.3**.

## Smoke test results

```
uv run pytest tests/uploads/test_ingest_status.py tests/uploads/test_upload_api.py -q
→ passed
```

## Commercial mapping

OR-05 / OR-06 — knowledge upload + freshness visibility.
