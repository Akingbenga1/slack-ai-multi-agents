# Task 34.1 journal

## Status

`completed`

## Summary

Introduced `PaymentProvider` Strategy + `get_payment_provider` Factory and `StripePaymentProvider` Adapter. Checkout, portal, customer-create, and webhook verify/handle go through the provider; product facades no longer `import stripe`. Entitlements / `require_entitlement` unchanged.

## Acceptance criteria checklist

- [x] Billing product code talks to a `PaymentProvider`; Stripe is one adapter
- [x] Ensure-customer, checkout URL, portal URL, webhook verify + handle are on the interface
- [x] Entitlement gating remains independent of the payment vendor

## Decision log

- **Patterns:** Strategy (`PaymentProvider`) + Factory (`get_payment_provider`) + Adapter (`StripePaymentProvider` / Stripe SDK). `stripe_client.py` stays as adapter-internal configure helpers.
- **`BillingError`** moved to `errors.py` to avoid circular imports (customers ↔ adapter).
- **`create_stripe=`** kept as deprecated alias for `create_external=` on `ensure_billing_customer`.
- Webhook URL `POST /billing/webhooks/stripe` kept (adapter-owned); routes call provider verify/handle. Full Template Method deferred to Task 34.3.
- `PAYMENT_PROVIDER` setting added early so the factory matches Sprint 33’s LLM pattern (documented in 34.2).

## Needs human

None new (existing Stripe test-key smoke still in project rollup).

## Files changed

- `api/app/billing/provider.py` (new)
- `api/app/billing/stripe_adapter.py` (new)
- `api/app/billing/errors.py` (new)
- `api/app/billing/customers.py`, `checkout.py`, `portal.py`, `webhooks.py`, `routes.py`, `__init__.py`
- `api/app/settings.py` (`payment_provider`)
- `tests/billing/test_provider_factory.py` (new)

## Resume notes

Done. Continue Task 34.2 — provider-neutral persistence columns + `.env.example`.

## Open questions

None.
