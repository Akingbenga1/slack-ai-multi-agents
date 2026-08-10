# Task 17.2 — Tenant schedule config fields

## Steps

- [x] Store `schedules.recurring_report` on `agent_configs` (enabled + channel + cadence + window)
- [x] Helpers: get / set / list due tenants (enabled + channel required)
- [x] `GET`/`PATCH /jobs/recurring-report/schedule` API
- [x] Seed default (disabled) on demo agent config
- [x] Light tests + docs

## Acceptance criteria

- [x] Org can set channel, cadence (`daily`/`weekly`), and enable flag
- [x] Defaults safe (disabled until configured)
- [x] Due-list helper ready for Beat (17.3)
