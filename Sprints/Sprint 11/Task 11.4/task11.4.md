# Task 11.4 — Webhooks

## Steps

- [x] `POST /billing/webhooks/stripe` — raw body + Stripe signature verify (`STRIPE_WEBHOOK_SECRET`)
- [x] Handle `checkout.session.completed` → set subscription id + activate plan
- [x] Handle `customer.subscription.updated` → sync plan active/inactive from Stripe status
- [x] Handle `customer.subscription.deleted` → deactivate plan
- [x] Resolve tenant via Checkout `client_reference_id` / metadata / `stripe_customer_id`
- [x] Light mocked tests + docs (webhook URL, events, Needs human)

## Acceptance criteria

- [x] Signed webhook events update `billing_customers.plan_status` + `stripe_subscription_id`
- [x] Invalid / missing signature → 401/503 (fail closed)
- [x] Unknown events acknowledged (2xx) without error
- [x] Checkout pay path can activate; cancel/delete path can deactivate (mocked)
