# Task 11.1 — Stripe customers linked to tenants

## Steps

- [x] Add Stripe SDK dependency + settings already present (`STRIPE_*`)
- [x] Billing module: create/retrieve Stripe Customer for a tenant (`client_id`)
- [x] Persist `billing_customers` row (`stripe_customer_id`, `plan_status=inactive`)
- [x] Call ensure on org/tenant provision (demo seed + shared helper for signup/checkout)
- [x] Light unit tests with mocked Stripe
- [x] Document env vars / Needs human for live keys

## Acceptance criteria

- [x] Given a tenant, create-or-retrieve yields a stable Stripe customer id linked 1:1
- [x] `billing_customers.tenant_id` unique; metadata carries `tenant_id`
- [x] Missing Stripe secret: local row still ensured; Stripe id deferred (mock/journal)
- [x] Ready for Checkout (11.2) and Portal (11.3)
