# Task 11.3 — Customer Portal session

## Steps

- [x] `POST /billing/portal-session` → Stripe Billing Portal URL
- [x] Require existing `stripe_customer_id` (ensure first if needed)
- [x] Return URL → `/app/billing`
- [x] Wire Manage billing CTA on `/app/billing`
- [x] Light mocked tests + docs

## Acceptance criteria

- [x] Org admin can open Customer Portal for their tenant’s Stripe customer
- [x] Missing customer / Stripe config → clear error
