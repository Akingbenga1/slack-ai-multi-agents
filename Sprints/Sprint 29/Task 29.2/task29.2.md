# Task 29.2 — `@tenant_job` (or base runner)

## Steps

- [x] Extract Template Method for session + job meta + running/success/fail + usage
- [x] Domain Celery tasks only call ingest / sync / report bodies
- [x] Support optional fail-path usage (recurring report)
- [x] Keep task names, kinds, and enqueue helpers stable
- [x] Update failure-logging test if import path moves

## Acceptance criteria

- [x] Heartbeat / ingest_upload / slack_history_sync / recurring_report share one lifecycle shell
- [x] No duplicated try/create/mark/usage/finally blocks in those task bodies
- [x] Existing worker behavior (kinds, usage events, fail marking) preserved
