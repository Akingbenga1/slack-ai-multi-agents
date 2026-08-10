# Task 12.4 journal

## Status

`completed`

## Summary

Added `build_usage_summary` (aggregates by `event_type` + budget headroom) and authenticated `GET /usage/summary?window=day|month`. Org portal `/app/usage` consumes it. Sprint 12 exit met in code: rate/budget limits + usage visible via API.

## Acceptance criteria checklist

- [x] Tenant-scoped aggregates via API
- [x] Suitable for org logs/usage page
- [x] Sprint 12 exit (limits + usage API)

## Decision log

- Window = UTC calendar `day` | `month` (aligned with budget windows).
- Include budget slices in the same payload so the portal does not need a second call.
- Thin `/app/usage` page now; richer event logs later (J8 / later sprint).

## Needs human

None new (inherited Slack + Stripe live verify).

## Files changed

- `api/app/governance/summary.py`
- `api/app/governance/routes.py`
- `api/app/governance/__init__.py`
- `api/app/main.py`
- `tests/governance/test_summary.py`
- `docs/governance.md`
- `web/components/UsageSummaryPanel.tsx`
- `web/app/app/usage/page.tsx`
- `web/app/app/page.tsx`
- `Sprints/Sprint 12/Task 12.4/*`

## Resume notes

Sprint 12 complete. Next: **Continue Sprint 13 from Task 13.1**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/governance -q  → 20 passed
```
