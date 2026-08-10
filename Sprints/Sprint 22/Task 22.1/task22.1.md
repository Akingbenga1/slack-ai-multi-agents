# Task 22.1 — First-org hardening pass

## Steps

- [x] Demo seed: optional `DEMO_ACTIVATE_PLAN` + Slack install fixture + report channel env
- [x] Gate sync / upload / recurring-report enqueue on active plan + entitlements
- [x] Beat due-lists skip inactive / unentitled tenants
- [x] First-org hardening smoke (script + pytest with mocks)
- [x] Docs: billing / governance / thin demo readiness notes; align smoke `--client-id` docs to `DEMO_TENANT_ID`

## Acceptance criteria

- [x] One demo org can be seeded into a demo-ready state without live Stripe (env flag)
- [x] Unpaid tenants cannot enqueue sync / ingest / report jobs
- [x] Hardening smoke proves seed → deny/allow → admin/MCP paths with fixtures (no live Slack/Stripe required)
