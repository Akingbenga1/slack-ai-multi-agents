# Task 34.4 journal

## Status

`completed`

## Summary

Org `/app/billing` (plus home link + inactive-plan banner) now talks **pay / manage subscription**. Stripe naming is limited to the adapter-secret footnote when `billing.provider=stripe`. Billing + Sprint 32 override tests green; `import stripe` only in `stripe_adapter` / `stripe_client`. Sprint 34 exit met; `review.md` payment-gateway gap marked implemented.

## Acceptance criteria checklist

- [x] Org `/app/billing` talks “pay / manage subscription,” not Stripe, unless the Stripe adapter is selected
- [x] Checkout + cancel still activate/deactivate entitlements; Sprint 32 override tests still pass
- [x] Sprint 34 exit: billing product code does not import Stripe (or PayPal) by name; Stripe is the first adapter

## Decision log

- Primary UX is vendor-neutral; Stripe key names appear only when the loaded billing row’s `provider` is `stripe` (adapter selected).
- Admin `/admin` plan-override copy that mentions Stripe webhooks / `plan_source` left as-is (operator semantics, not org self-serve billing).

## Needs human

None new (existing Stripe live keys / webhook Needs-human remain).

## Files changed

- `web/app/app/billing/page.tsx`
- `web/components/BillingActions.tsx`
- `web/app/app/page.tsx`
- `web/components/PortalStatusBanners.tsx`
- `docs/portal.md`, `docs/billing.md`
- `Project-Documents/review.md`

## Smoke test results

- `uv run pytest tests/billing tests/admin/test_plan_override_sprint32.py -q` → **28 passed**

## Resume notes

**Sprint 34 complete.** Next Ralph batch: **Continue Sprint 35 from Task 35.1** — `VectorStore` + Qdrant adapter.

## Open questions

None.
