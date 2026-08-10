# Task 5.4 journal

## Status

`completed`

## Summary

Added `POST /jobs/heartbeat` (Bearer JWT required) that enqueues `worker.heartbeat` for the caller's tenant via `enqueue_heartbeat()`. Org admin cross-tenant rejected; platform_owner may pass `tenant_id` / `X-Client-Id`. Missing auth returns 401. Sprint 5 complete.

## Acceptance criteria checklist

- [x] Unauthenticated → 401 — done (`HTTPBearer(auto_error=False)` + explicit 401 in `get_current_principal`)
- [x] Cross-tenant → 403 — done (`require_tenant_access` + body tenant check)
- [x] Enqueue returns `task_id`; worker runs with `client_id` — done (smoke: message `api-stub-5.4-final`)

## Decision log

- Path: `POST /jobs/heartbeat` (internal stub under `/jobs`, not Slack-facing).
- Response: `{ task_id, client_id, queue, kind }` — fire-and-forget (no wait).
- Missing Bearer: 401 (aligned acceptance; was FastAPI default 403 before deps tweak).

## Needs human

None for this task. (Sprint 4 Slack live verify still open at project level.)

## Files changed

- `api/app/jobs/routes.py`, `api/app/jobs/__init__.py`
- `api/app/main.py`, `api/app/auth/deps.py`
- `README.md`, `docs/celery.md`

## Resume notes

Sprint 5 exit met. Next: **Continue Sprint 6 from Task 6.1**.

## Open questions

None.

## Smoke test results

- No token → 401 `Not authenticated`
- org_admin + foreign `X-Client-Id` → 403
- org_admin enqueue → 200 + worker result `client_id=11111111-…` message `api-stub-5.4-final`
- platform_owner + `tenant_id` + `priority=10` → queue `high`
