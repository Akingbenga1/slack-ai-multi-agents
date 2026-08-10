# Task 12.2 journal

## Status

`completed`

## Summary

Active-plan entitlements now include `tokens_daily` / `tokens_monthly` / `jobs_daily`. `check_budget` / `require_budget` sum `usage_events` and reject over-cap job enqueues (heartbeat, slack sync, upload ingest) with HTTP 403. Inactive plan skips numeric budget by default (`require_active_plan` for Sprint 14).

## Acceptance criteria checklist

- [x] Active → default budgets; inactive → zeros on entitlements
- [x] Over budget → 403 `budget_exceeded`
- [x] Wired for 12.3 usage + later agent gating

## Decision log

- Budgets live in `entitlements` JSON (no new column / migration).
- Inactive plan does not hard-block jobs yet (demo without Stripe); use `require_active_plan=True` for agent.
- Job budget counted from `job`/`sync_run`/`ingest`/`report_post` event types.

## Needs human

None.

## Files changed

- `api/app/billing/plans.py`, `api/app/billing/__init__.py`
- `api/app/governance/budgets.py`
- `api/app/jobs/routes.py`, `api/app/uploads/routes.py`
- `tests/governance/test_budgets.py`
- `docs/governance.md`, `docs/billing.md`

## Resume notes

Next in batch: **Task 12.3 — Usage event recording**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/governance tests/billing -q  → 32 passed
```
