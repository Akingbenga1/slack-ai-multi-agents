# Task 20.1 journal

## Status

`completed`

## Summary

Hardened org billing UX on top of Sprint 11 Stripe APIs: clearer unpaid/active copy, status-aware Checkout/Portal CTAs, and short polling after Checkout success until `plan_status=active`.

## Acceptance criteria checklist

- [x] Start Checkout from portal
- [x] Open Customer Portal from portal
- [x] Plan status visible + post-checkout poll
- [x] OR-02

## Decision log

- Reused `POST /billing/checkout-session` and `/billing/portal-session` (no new Stripe endpoints).
- Poll ≤8 attempts / 2s after `checkout=success` so webhook lag is visible without a long spinner.

## Needs human

Stripe test keys + live Checkout/Portal/webhook still required (`docs/billing.md`).

## Files changed

- `web/components/BillingActions.tsx`, `web/app/app/billing/page.tsx`, `web/app/app/page.tsx`
- `docs/portal.md`
- `Sprints/Sprint 20/Task 20.1/*`

## Resume notes

Next in batch: **Task 20.2**.

## Commercial mapping

OR-02 — pay / manage payment via Stripe in the portal.
