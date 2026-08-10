# Task 11.3 journal

## Status

`completed`

## Summary

`POST /billing/portal-session` ensures the Stripe customer and returns a Customer Portal URL (payment method / cancel). `/app/billing` Manage billing button redirects into the portal. Mocked unit tests cover the happy path.

## Acceptance criteria checklist

- [x] Portal URL for tenant customer — done (mocked)
- [x] Missing Stripe config → clear error — done

## Decision log

- Portal return URL is `{WEB_APP_URL}/app/billing`.
- Same `BillingActions` component drives Checkout + Portal CTAs.

## Needs human

Stripe test keys + enable Customer Portal in Stripe Dashboard for live verify. Webhook activation still Task 11.4.

## Files changed

- `api/app/billing/portal.py`, `routes.py`
- `web/components/BillingActions.tsx`, `web/app/app/billing/page.tsx`
- `tests/billing/test_checkout_portal.py`
- `docs/billing.md`

## Resume notes

Batch 11.1–11.3 complete. Next: **Continue Sprint 11 from Task 11.4** (webhooks).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/billing -q  → 9 passed
```
