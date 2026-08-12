# Task 34.2 journal

## Status

`completed`

## Summary

Renamed Stripe-named billing columns to provider-neutral `provider` / `external_customer_id` / `external_subscription_id` with Alembic migration copying existing Stripe ids. Documented `PAYMENT_PROVIDER` in `.env.example` and `docs/billing.md`; API + admin/org UI field names updated.

## Acceptance criteria checklist

- [x] DB + API use provider-neutral external ids; Stripe ids migrate in place
- [x] Switching provider is an env selector; Stripe secrets keep their names
- [x] PayPal is not a live second checkout in this sprint

## Decision log

- Migration `c1d4e85a9f70` copies then drops `stripe_*` columns; unique constraint moves to `external_customer_id`.
- `apply_plan_state(..., stripe_subscription_id=)` kept as deprecated alias.
- `plan_source` values remain `admin` \| `stripe` (Stripe adapter id) — admin lock semantics unchanged.
- PayPal factory path raises a clear “not implemented” error; no PayPal env keys.

## Needs human

- Optional: `alembic upgrade head` (`c1d4e85a9f70`) on local/demo DB before live billing smoke.

## Files changed

- `api/app/db/models.py`
- `alembic/versions/c1d4e85a9f70_billing_provider_ids.py`
- `api/app/billing/plans.py`, `customers.py`, `checkout.py`, `portal.py`, `webhooks.py`, `routes.py`
- `api/app/admin/tenants.py`
- `api/app/settings.py`, `.env.example`, `docs/billing.md`
- `web/components/BillingActions.tsx`, `TenantDetailPanel.tsx`
- billing / admin / governance tests + smoke script field renames

## Resume notes

Done. Continue Task 34.3 — webhook Template Method (verify → map → `apply_plan_state`).

## Open questions

None.
