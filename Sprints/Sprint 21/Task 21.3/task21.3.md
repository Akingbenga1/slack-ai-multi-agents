# Task 21.3 — Suspend / override budget controls

## Steps

- [x] `audit_logs` migration + model
- [x] `PATCH /admin/tenants/{id}/status` (active|suspended) + audit
- [x] `PATCH /admin/tenants/{id}/budgets` + audit
- [x] `GET /admin/audit-logs`
- [x] Suspended tenants blocked in `plan_is_active` / Slack agent reply
- [x] Detail UI support actions

## Acceptance criteria

- [x] Owner can suspend/unsuspend and override budgets with audit trail
- [x] Suspended org gets clear Slack denial
