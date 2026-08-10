# Task 11.2 journal

## Status

`completed`

## Summary

`POST /billing/checkout-session` ensures the Stripe customer, creates a subscription Checkout Session for `STRIPE_PRICE_ID`, and returns the hosted URL. Org portal `/app/billing` with Subscribe CTA redirects into Checkout. Mocked unit tests cover missing keys and happy path.

## Acceptance criteria checklist

- [x] Checkout URL for tenant customer — done (mocked)
- [x] Missing price/secret → 400 / BillingError — done
- [x] `/app/billing` starts Checkout — done

## Decision log

- Success/cancel URLs use `WEB_APP_URL` → `/app/billing?checkout=success|cancel`.
- Plan activation still deferred to webhooks (11.4); success banner notes that.

## Needs human

`STRIPE_SECRET_KEY` + `STRIPE_PRICE_ID` (test mode) for live Checkout — see `docs/billing.md`.

## Files changed

- `api/app/billing/checkout.py`, `routes.py`
- `web/app/app/billing/page.tsx`, `web/components/BillingActions.tsx`
- `tests/billing/test_checkout_portal.py`
- `docs/billing.md`, `README.md`

## Resume notes

Next in batch: **Task 11.3 — Customer Portal session**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/billing -q  → 9 passed
```
