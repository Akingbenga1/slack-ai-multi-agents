# Task 12.4 — Usage summary API

## Steps

- [x] Aggregate helper: sum/count `usage_events` by `event_type` for a tenant window
- [x] Include budget snapshot (tokens daily/monthly, jobs daily) for the org logs page
- [x] Authenticated `GET /usage/summary` (tenant-scoped; optional `window=day|month`)
- [x] Light org portal page `/app/usage` consuming the API
- [x] Light tests + docs

## Acceptance criteria

- [x] Org can read tenant usage aggregates via API (isolated by tenant)
- [x] Response suitable for org logs/usage page (by event type + budget headroom)
- [x] Sprint 12 exit: over-limit blocked (12.1–12.2) + usage visible via API
