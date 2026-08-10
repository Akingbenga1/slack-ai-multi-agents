# Task 11.2 — Checkout Session API + Next.js billing start page

## Steps

- [x] `POST /billing/checkout-session` (auth + tenant); ensure customer; create Session
- [x] Use `STRIPE_PRICE_ID`; success/cancel → `/app/billing`
- [x] Next.js `/app/billing` start page (subscribe CTA)
- [x] Light tests with mocked Stripe Session.create
- [x] Docs update

## Acceptance criteria

- [x] Authenticated org admin gets a Checkout URL for the tenant’s Stripe customer
- [x] Missing price/secret → clear 400 (fail closed)
- [x] `/app/billing` can start Checkout via API
