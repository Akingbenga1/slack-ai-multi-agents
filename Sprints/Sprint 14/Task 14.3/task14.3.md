# Task 14.3 — Inactive plan / over-budget messaging

## Steps

- [x] Before agent invoke: require active plan + `agent` entitlement
- [x] Check token budget with `require_active_plan=True`
- [x] Post clear Slack reply when plan inactive / over budget (no LangGraph)
- [x] Light tests + docs

## Acceptance criteria

- [x] Inactive / no-agent entitlement → clear Slack denial (no agent run)
- [x] Over token budget → clear Slack denial (no agent run)
