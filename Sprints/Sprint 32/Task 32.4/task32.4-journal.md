# Task 32.4 journal

## Status

completed

## Summary

Added `tests/admin/test_plan_override_sprint32.py` covering entitlement gates after activate/deactivate, suspend independence, Stripe checkout regression for paying customers, and `ALLOW_PLAN_WAIVERS` HTTP 403.

## Acceptance criteria checklist

- [x] Activate/deactivate entitlements gate agent/ingest/sync
- [x] Suspend blocks usage independently of plan override
- [x] Org billing checkout path unchanged for stripe-managed rows

## Decision log

- Used sqlite in-memory + `AuditLog` table for action-layer tests; HTTP test reuses `_FakeDB` from admin API tests.

## Needs human

(none)

## Files changed

- `tests/admin/test_plan_override_sprint32.py`

## Resume notes

**Sprint 32 complete.** Next Ralph batch: **Sprint 33 / Task 33.1** — LLM adapters + factory.

## Open questions

(none)

## Smoke test results

`uv run pytest tests/admin/test_plan_override_sprint32.py tests/admin/test_admin_api.py tests/billing/test_webhooks.py -q` — 20 passed
