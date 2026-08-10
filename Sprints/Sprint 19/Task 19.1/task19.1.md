# Task 19.1 — Agent settings pages

## Steps

- [x] Add GET/PATCH `/agent/config` for name, system_prompt, allowlist (tenant-scoped)
- [x] Org portal `/app/agent` UI: edit name / prompt / channel allowlist
- [x] Wire schedules enable/disable (Slack sync + recurring report) into the same page via existing jobs APIs
- [x] Persist org system_prompt as compose overlay when set
- [x] Light API + docs pointer

## Acceptance criteria

- [x] Org admin can view/update agent name, instructions, allowlist without platform owner
- [x] Org admin can enable/disable sync + recurring report jobs and edit report schedule fields
- [x] Cross-tenant PATCH denied for org_admin
- [x] OR-03 / OR-04 covered for MVP self-serve settings
