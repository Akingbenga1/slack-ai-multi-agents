# Task 20.2 journal

## Status

`completed`

## Summary

Added tenant-scoped `GET /usage/events` and `GET /usage/jobs`, and expanded `/app/usage` into a logs viewer (filters for mentions/tokens/jobs + failed jobs).

## Acceptance criteria checklist

- [x] Mentions / tokens / jobs / errors visible
- [x] Cross-tenant denied
- [x] Summary + budgets retained

## Decision log

- Kept aggregates on `/usage/summary`; detail lists are separate endpoints for simple filtering.
- Jobs table is the error surface (`status=failed` + `error` column) rather than inventing a parallel error log.

## Needs human

None new.

## Files changed

- `api/app/governance/logs.py`, `routes.py`
- `web/components/UsageSummaryPanel.tsx`, `web/app/app/usage/page.tsx`
- `tests/governance/test_logs.py`
- `docs/governance.md`, `docs/portal.md`
- `Sprints/Sprint 20/Task 20.2/*`

## Resume notes

Next in batch: **Task 20.3**.

## Smoke test results

```
uv run pytest tests/governance/test_logs.py tests/governance/test_summary.py -q
→ 10 passed
```

## Commercial mapping

OR-07 — view logs and usage for the tenant.
