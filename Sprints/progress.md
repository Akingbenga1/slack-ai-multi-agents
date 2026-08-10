# Project progress (Ralph loop)

- **Active sprint:** Sprint 30 (complete)
- **Last completed task:** 30.4
- **Current / next task:** none — pattern-upgrade sprints (25–30) finished per `jira-task.md`
- **Batch in progress:** none (Sprint 30 / Task 30.4 verification done)

- **Open Needs human:**

  - Slack app credentials + tunnel URLs + live Events verify + OAuth install + grounded mention/DM Q&A (`docs/slack-app-setup.md`; journals 4.1–4.4, 14.1–14.4)

  - Reinstall Slack app after history scopes (`channels:*` / `groups:*`) + live sync → Qdrant verify (Sprint 9 exit)

  - **Sprint 23:** reinstall Slack app after `files:read` / `files:write` for live attachment download + PDF upload + title edit (`docs/slack-app-setup.md`, `docs/slack-file-actions.md`)

  - **Sprint 24:** live Slack verify of workflow store / list / copy / advise / J11 combined ask after file scopes reinstall (`docs/workflow-library.md`)

  - Stripe test keys (`STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`) + Customer Portal + webhook URL + live Checkout/Portal activate/deactivate (`docs/billing.md`; journals 11.1–11.5) — needed for active plan before Slack agent answers

  - Optional: `ANTHROPIC_API_KEY` for live (non-stub) agent compose (`docs/agent.md`; journals 13.1–13.4, 14.4)

  - Recurring report live verify: set `/jobs/recurring-report/schedule` channel + `POST /jobs/recurring-report` (or Beat) → message in channel (Sprint 17 exit)

  - Optional: Slack mention “start onboarding” or MCP Inspector `start_onboarding` for Sprint 18 exit live verify (`docs/onboarding.md`)

  - Optional: portal smoke — `admin@example.com` → `/app/agent`, `/app/knowledge`, `/app/billing`, `/app/usage`, `/app/slack` with API + Celery worker (`docs/portal.md`)

  - Optional: admin portal smoke — `owner@example.com` → `/admin/tenants`, `/admin/health` (`docs/admin-portal.md`)

  - Optional: `DEMO_ACTIVATE_PLAN=true` (+ Slack/report env) for laptop demo without Checkout (`docs/demo-readiness.md`)

  - Optional: second-org live Slack workspace install after `POST /admin/tenants` / `scripts/second_org_smoke.py` (`docs/demo-readiness.md`)

- **Active sprint folder:** `Sprints/Sprint 30/`
