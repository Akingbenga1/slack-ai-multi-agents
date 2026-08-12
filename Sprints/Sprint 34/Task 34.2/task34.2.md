# Task 34.2 — Provider-neutral persistence

## Steps

- [x] Replace `stripe_customer_id` / `stripe_subscription_id` with `provider`, `external_customer_id`, `external_subscription_id` (Alembic migrate existing Stripe ids)
- [x] Wire `PAYMENT_PROVIDER=stripe|paypal` (demo default `stripe`) through settings + factory
- [x] Keep `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`, Next.js `STRIPE_PUBLISHABLE_KEY` as Stripe-adapter secrets
- [x] PayPal remains documented extension / stub — no PayPal env keys
- [x] Update `.env.example`: selector + existing Stripe keys as adapter secrets
- [x] Update API / admin / portal field names to provider-neutral ids
- [x] Light smoke: billing + plan-override tests green

## Acceptance criteria

- [x] DB + API use provider-neutral external ids; Stripe ids migrate in place
- [x] Switching provider is an env selector; Stripe secrets keep their names
- [x] PayPal is not a live second checkout in this sprint
