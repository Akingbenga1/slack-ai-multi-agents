# Task 9.5 — Sync status read API

## Steps

- [x] Domain helper: last success/failure job + watermarks + schedule/install flags
- [x] Auth-required `GET /jobs/slack-history-sync/status`
- [x] Light unit tests + docs

## Acceptance criteria

- [x] Portal can read last success and last failure for the tenant
- [x] Unauthenticated → 401; cross-tenant → 403
