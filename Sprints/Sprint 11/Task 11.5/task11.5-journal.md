# Task 11.5 journal

## Status

`completed`

## Summary

Per-tenant plan fields live on `billing_customers`: `plan_status`, `stripe_subscription_id`, plus new `entitlements` JSON (`agent` / `ingest` / `sync`). Webhook plan updates sync entitlements. Portal billing page shows status; helpers ready for Sprint 12+ / Slack inactive messaging.

## Acceptance criteria checklist

- [x] Active grants entitlements; inactive clears — done
- [x] Org portal reads plan fields — done (`/billing/customers/me` + UI)
- [x] Helpers for later sprints — `plan_is_active`, `tenant_has_entitlement`

## Decision log

- Kept plan fields on `billing_customers` (1:1 with tenant) rather than duplicating onto `tenants`.
- Default active entitlements: agent + ingest + sync (budgets refine in Sprint 12).
- Migration `b7c2e91f4a10_billing_entitlements`.

## Needs human

Same Stripe live verify as 11.1–11.4 (test keys + webhook + Checkout/Portal). No new secrets beyond `STRIPE_WEBHOOK_SECRET`.

## Files changed

- `api/app/db/models.py`, `api/app/billing/plans.py`, `customers.py`, `routes.py`, `__init__.py`
- `alembic/versions/b7c2e91f4a10_billing_entitlements.py`
- `tests/billing/test_plans.py`, `test_webhooks.py`
- `web/components/BillingActions.tsx`
- `docs/billing.md`

## Resume notes

Sprint 11 complete in code. Next: **Continue Sprint 12 from Task 12.1** (per-tenant rate limit at gateway).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/billing -q  → 17 passed
uv run alembic upgrade head     → b7c2e91f4a10 applied
```

## Schema / migration notes

- Column `billing_customers.entitlements` JSONB NOT NULL default `{}`.
