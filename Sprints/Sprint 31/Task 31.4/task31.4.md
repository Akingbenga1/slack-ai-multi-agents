# Task 31.4 — Regression vs owner provisioning

## Steps

- [x] Platform owner can still create tenants via `/admin/tenants` after self-signup exists
- [x] Existing demo seed / `DEMO_ACTIVATE_PLAN` still works; self-signup must not require it
- [x] No new env keys required for signup itself (reuse JWT / NextAuth / public URLs)
- [x] Document: Sprint 18 Slack onboarding stub is unchanged and is **not** tenant signup
- [x] Light smoke: signup + admin create + demo seed + onboarding stub

## Acceptance criteria

- [x] `POST /admin/tenants` still provisions a distinct org (owner JWT) after a public signup
- [x] `DEMO_ACTIVATE_PLAN` still activates the **demo seed** tenant; self-signup plan stays inactive
- [x] `.env.example` / `Settings` gain no signup-specific keys
- [x] Docs state Slack `start_onboarding` stub ≠ `/signup` tenant registration
