# Task 32.1 journal

## Status

completed

## Summary

Added `PATCH /admin/tenants/{id}/plan` so the platform owner can activate or deactivate plan entitlements on an **existing** tenant without Stripe Checkout. New columns `billing_customers.plan_source` (`admin`|`stripe`) and `override_reason` persist operator waivers; Stripe webhook handlers skip rows where `plan_source=admin`. Create-time `activate_plan` and `DEMO_ACTIVATE_PLAN` now set `plan_source=admin` for consistency.

## Acceptance criteria checklist

- [x] `PATCH /admin/tenants/{id}/plan` with `{ "plan_status": "active"|"inactive", "reason": "…" }`
- [x] Writes `plan_status` / entitlements; audits `tenant.plan.override`
- [x] Admin waiver blocks silent Stripe webhook overwrite
- [x] Create-time activate paths unchanged in behaviour; set `plan_source=admin`

## Decision log

- `plan_status=active` → `plan_source=admin` (waiver); `plan_status=inactive` → `plan_source=stripe` (restore Stripe control).
- Webhook handlers set `plan_source=stripe` and clear `override_reason` when they apply Stripe-driven changes.
- `ALLOW_PLAN_WAIVERS` env deferred to Task 32.3 (semantics + guardrail).
- No Strategy/Factory (Sprint 32 product gap).

## Needs human

- Optional: `alembic upgrade head` (`a8f3b12c4d56`) before live admin plan override smoke.

## Files changed

- `alembic/versions/a8f3b12c4d56_billing_plan_source.py`
- `api/app/db/models.py` — `plan_source`, `override_reason`
- `api/app/billing/plans.py` — `plan_is_admin_locked`, extended `apply_plan_state`
- `api/app/billing/webhooks.py` — skip admin-locked rows; set `plan_source=stripe` on apply
- `api/app/admin/actions.py` — `override_tenant_plan`
- `api/app/admin/routes.py` — `PATCH /admin/tenants/{id}/plan`
- `api/app/admin/provision.py`, `api/app/membership.py` — admin plan source on create/seed
- `api/app/admin/tenants.py` — expose plan source in list/detail
- `tests/admin/test_admin_api.py`, `tests/billing/test_webhooks.py`
- `docs/admin-portal.md`

## Resume notes

Continue with **Task 32.2** — admin UI control on `/admin/tenants/[id]`.

## Open questions

(none)

## Smoke test results

`uv run pytest tests/admin/test_admin_api.py tests/billing/test_webhooks.py -q`
