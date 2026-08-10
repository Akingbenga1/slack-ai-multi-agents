# Task 24.2 — Slack “store this workflow file” path

Stories: `TM-20`, `TM-23` · Journey: `J11`

## Steps

- [x] Route intent → `workflow_store` (store / save to shared library)
- [x] Reuse Sprint 23.1 attachment download
- [x] Persist via workflow library + acknowledge in Slack
- [x] Idempotent re-store by content hash / Slack `file_id`
- [x] Usage event for store
- [x] Light tests for intent + idempotency

## Acceptance criteria

- [x] Mention/DM with attachment + store phrasing stores a shared template
- [x] Re-store of same file returns existing template (no duplicate shared row)
- [x] Clear success/failure confirmation (`TM-23`)
- [x] Tenant isolation on store
