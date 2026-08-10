# Task 12.2 — Token/job budgets from plan

## Steps

- [x] Default daily/monthly token + daily job budgets on active plan entitlements
- [x] Helpers: read budgets, sum usage in window, `check_budget` allow/deny
- [x] Reject over-budget API/job paths with clear error (`budget_exceeded`)
- [x] Clear budgets when plan inactive
- [x] Light tests + docs

## Acceptance criteria

- [x] Active plan grants default budgets; inactive → zero / deny
- [x] Over daily/monthly budget → request/job rejected (not silent)
- [x] Ready for usage recording (12.3) and Slack inactive messaging (14.x)
