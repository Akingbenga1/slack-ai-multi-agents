# Task 34.3 — Webhook Template Method

## Steps

- [x] Shared pipeline: verify → map event → `apply_plan_state`
- [x] Per-processor event map lives on the Stripe adapter (`map_webhook_event`)
- [x] Keep `POST /billing/webhooks/stripe` working (adapter-owned URL)
- [x] Light smoke: existing webhook tests green via Template Method path

## Acceptance criteria

- [x] Webhook handling uses a shared Template Method; Stripe only supplies the event map
- [x] Stripe Dashboard webhook URL continues to work
- [x] Admin plan lock + entitlement updates still apply correctly
