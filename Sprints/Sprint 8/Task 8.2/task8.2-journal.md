# Task 8.2 journal

## Status

`completed`

## Summary

Added tenant-scoped multipart `POST /uploads` with `file_role=document|slack_history`, extension allowlists, and on-disk storage under `UPLOAD_DIR/{client_id}/`. Auth via existing JWT + `require_tenant_access`; cross-tenant rejected for org users.

## Acceptance criteria checklist

- [x] Authenticated upload scoped to tenant — done
- [x] document extensions — done
- [x] slack_history extensions — done
- [x] unauth / cross-tenant rejected — done

## Decision log

- No DB upload table yet; metadata returned in JSON; path is enough for Celery ingest (8.3).
- Max body 50 MiB guard on the route.
- Status field reserved: `stored` now, `queued` after enqueue in 8.3.

## Needs human

None.

## Files changed

- `api/app/uploads/` (roles, storage, routes)
- `api/app/settings.py`, `api/app/main.py`
- `tests/uploads/test_upload_api.py`
- `docs/uploads.md`, `.env.example`

## Resume notes

Next: **Task 8.3 — Ingest job for uploads** (Celery: parse → chunk → TEI → Qdrant; wire enqueue from upload).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/uploads -q  → 6 passed
```
