# Task 11.1 journal

## Status

`completed`

## Summary

Added `api/app/billing/` with idempotent `ensure_billing_customer` (local `billing_customers` row + Stripe `Customer.create` when `STRIPE_SECRET_KEY` is set). Demo seed wires ensure for the demo tenant. `POST /billing/customers/ensure` and `GET /billing/customers/me` expose the link. Unit tests mock Stripe.

## Acceptance criteria checklist

- [x] Create/retrieve stable Stripe customer linked 1:1 — done (mocked)
- [x] Metadata `tenant_id` / `client_id` — done
- [x] Missing secret → local row, no Stripe id — done
- [x] Ready for 11.2 / 11.3 — done

## Decision log

- No full org signup API yet (demo auth); ensure is called from seed + HTTP ensure + later Checkout.
- Without Stripe keys, fail soft on customer create (row only); Checkout/Portal fail closed.

## Needs human

Stripe **test** `STRIPE_SECRET_KEY` (+ later price/webhook) in `.env` — see `docs/billing.md`.

## Files changed

- `api/app/billing/` (`customers`, `stripe_client`, `routes`, `__init__`)
- `api/app/membership.py`, `api/app/main.py`, `api/app/settings.py`
- `tests/billing/test_customers.py`
- `docs/billing.md`, `.env.example`, `pyproject.toml` / `uv.lock`
- `Sprints/Sprint 11/Task 11.1/*`

## Resume notes

Next in batch: **Task 11.2 — Checkout Session API + Next.js billing start page**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/billing -q  → 5 passed
```
