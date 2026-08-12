# Task 34.4 — Portal copy + tests

## Steps

- [x] Org `/app/billing` (and related org portal CTAs) talk “pay / manage subscription,” not Stripe — Stripe naming only when that adapter is selected (e.g. adapter-secret footnote)
- [x] Update `docs/portal.md` / light billing docs for vendor-neutral org copy
- [x] Smoke: checkout + cancel / entitlement paths still green (`tests/billing`)
- [x] Smoke: Sprint 32 plan-override tests still pass
- [x] Confirm billing product code does not `import stripe` outside the Stripe adapter (Sprint 34 exit)
- [x] Mark payment-gateway gap implemented in `Project-Documents/review.md`

## Acceptance criteria

- [x] Org `/app/billing` talks “pay / manage subscription,” not Stripe, unless the Stripe adapter is selected
- [x] Checkout + cancel still activate/deactivate entitlements; Sprint 32 override tests still pass
- [x] Sprint 34 exit: billing product code does not import Stripe (or PayPal) by name; Stripe is the first adapter
