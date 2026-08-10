# Task 2.3 — Tenant context helpers

## Steps

- [x] Add `client_id` contextvar + get/set helpers
- [x] FastAPI middleware: read `X-Client-Id` into context
- [x] Celery: propagate `client_id` via task headers / before_task hooks
- [x] Structured logging filter/formatter includes `client_id` when present
- [x] Light smoke: request with header returns client_id

## Acceptance criteria

- [x] Request path can resolve/attach `client_id`
- [x] Celery tasks can carry `client_id` in headers
- [x] Logs include `client_id` when set
