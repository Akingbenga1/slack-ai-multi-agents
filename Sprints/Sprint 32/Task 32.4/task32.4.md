# Task 32.4 — Tests

## Checklist

- [x] Activate/deactivate existing tenant; entitlements gate agent/ingest/sync
- [x] Suspend blocks usage independently of plan override
- [x] Checkout still works for stripe-managed customer (OR-02)
- [x] ALLOW_PLAN_WAIVERS guardrail (unit + HTTP 403)

## Acceptance criteria

- [x] Regression tests in `tests/admin/test_plan_override_sprint32.py`
- [x] Existing admin + webhook tests still green
