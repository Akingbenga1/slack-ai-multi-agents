# Task 34.1 — `PaymentProvider` + Stripe adapter

## Steps

- [x] Define `PaymentProvider` Strategy: ensure-customer, checkout URL, portal URL, webhook verify + handle
- [x] Implement `StripePaymentProvider` Adapter (owns Stripe SDK / `stripe_client` helpers)
- [x] Move Checkout / Customer Portal / customer-create Stripe calls behind the adapter
- [x] Thin product facades (`checkout.py` / `portal.py` / `customers.py`) call the provider — no `import stripe` outside the adapter
- [x] Keep `plan_status` / entitlements (`agent` / `ingest` / `sync`) / `require_entitlement` vendor-neutral
- [x] Light smoke: checkout/portal/customer tests still pass via mocked Stripe

## Acceptance criteria

- [x] Billing product code talks to a `PaymentProvider`; Stripe is one adapter
- [x] Ensure-customer, checkout URL, portal URL, webhook verify + handle are on the interface
- [x] Entitlement gating remains independent of the payment vendor
