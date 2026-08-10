# Task 2.3 journal

## Status

`completed`

## Summary

Added tenant context (`api/app/tenant.py`), FastAPI `TenantContextMiddleware` (`X-Client-Id`), structured logging with `client_id=…`, and Celery header inject/restore on `worker/celery_app.py`.

## Acceptance criteria checklist

- [x] Request attaches `client_id` — done (`/debug/tenant`)
- [x] Celery headers — done (`before_task_publish` / `task_prerun`)
- [x] Logs include `client_id` — done (`ClientIdFilter`)

## Decision log

- Header name: `X-Client-Id` (UUID preferred; non-empty slug allowed for scaffold).
- Celery uses task header key `client_id`.

## Needs human

None.

## Files changed

- `api/app/tenant.py`, `middleware.py`, `logging_config.py`, `main.py`
- `worker/celery_app.py`, `worker/__init__.py`

## Resume notes

Task 2.4 deep health in same batch.

## Open questions

None.

## Smoke test results

- `GET /debug/tenant` with `X-Client-Id: 11111111-…` → matching JSON
