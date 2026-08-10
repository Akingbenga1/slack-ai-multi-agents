# Task 11.5 — Plan fields on tenant

## Steps

- [x] Confirm / document `plan_status` + `stripe_subscription_id` on `billing_customers` (per-tenant)
- [x] Add `entitlements` JSONB (agent / ingest / sync flags) + Alembic migration
- [x] Sync entitlements when plan activates / deactivates (webhook path + shared helper)
- [x] Expose plan fields + entitlements on `GET /billing/customers/me`
- [x] Show plan status on `/app/billing`
- [x] Light tests + docs

## Acceptance criteria

- [x] Active plan → entitlements granted; inactive / canceled → entitlements cleared
- [x] Org portal can read current `plan_status` / subscription id / entitlements
- [x] Helper available for later sprints (governance / Slack inactive messaging)
