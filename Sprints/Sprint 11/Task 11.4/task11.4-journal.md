# Task 11.4 journal

## Status

`completed`

## Summary

Stripe webhook endpoint verifies signatures and applies plan lifecycle: Checkout completed activates the tenant plan; subscription updated/deleted syncs or clears `plan_status` / `stripe_subscription_id`. Entitlement flags are Task 11.5.

## Acceptance criteria checklist

- [x] Webhook updates plan fields — done (mocked)
- [x] Bad signature / missing secret fail closed — done
- [x] Unknown events 2xx — done
- [x] Activate / deactivate paths — done (mocked)

## Decision log

- Endpoint: `POST /billing/webhooks/stripe` (matches tunnel-plan / earlier docs).
- Active Stripe statuses: `active`, `trialing` → local `plan_status=active`; everything else inactive.
- Tenant resolve order: Checkout `client_reference_id` / metadata → billing row by customer/subscription id.

## Needs human

Configure Stripe Dashboard webhook to `{PUBLIC_BASE_URL}/billing/webhooks/stripe` (tunnel if local) for events `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`. Put signing secret in `STRIPE_WEBHOOK_SECRET`. Live pay→activate / cancel→deactivate still needs test keys from 11.1–11.3.

## Files changed

- `api/app/billing/webhooks.py`, `plans.py`, `routes.py`, `__init__.py`
- `tests/billing/test_webhooks.py`
- `docs/billing.md`, `docs/tunnel-plan.md`
- `web/app/app/billing/page.tsx` (success banner)

## Resume notes

Next in batch: **Task 11.5 — Plan fields on tenant** (entitlement flags).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/billing -q  → 16 passed
```
