# Project progress (Ralph loop)

- **Active sprint:** Sprint 47 (system-behaviour scenario tests) — **complete**
- **Last completed task:** 47.3
- **Current / next task:** none — all sprints through 47 complete
- **Batch in progress:** none (47.1–47.3 done this session — Sprint 47 complete)

- **Open Needs human:**

    - Slack app credentials + tunnel URLs + live Events verify + OAuth install + grounded mention/DM Q&A (`docs/slack-app-setup.md`; journals 4.1–4.4, 14.1–14.4)

    - Reinstall Slack app after history scopes (`channels:*` / `groups:*`) + live sync → Qdrant verify (Sprint 9 exit)

    - **Sprint 23:** reinstall Slack app after `files:read` / `files:write` for live attachment download + PDF upload + title edit (`docs/slack-app-setup.md`, `docs/slack-file-actions.md`)

    - **Sprint 24:** live Slack verify of workflow store / list / copy / advise / J11 combined ask after file scopes reinstall (`docs/workflow-library.md`)

    - Stripe test keys (`STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`) + Customer Portal + webhook URL + live Checkout/Portal activate/deactivate (`docs/billing.md`; journals 11.1–11.5) — needed for active plan before Slack agent answers

    - Optional: live chat compose — `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`, or `LLM_PROVIDER=ollama` + local Ollama; offline dry-runs use `LLM_PROVIDER=stub` (`docs/agent.md`; journals 13.1–13.4, 33.1–33.4)

    - Recurring report live verify: set `/jobs/recurring-report/schedule` channel + `POST /jobs/recurring-report` (or Beat) → message in channel (Sprint 17 exit)

    - Optional: Slack mention "start onboarding" or MCP Inspector `start_onboarding` for Sprint 18 exit live verify (`docs/onboarding.md`)

    - Optional: portal smoke — `admin@example.com` → `/app/agent`, `/app/knowledge`, `/app/billing`, `/app/usage`, `/app/slack` with API + Celery worker (`docs/portal.md`)

    - Optional: admin portal smoke — `owner@example.com` → `/admin/tenants`, `/admin/health` (`docs/admin-portal.md`)

    - Optional: `DEMO_ACTIVATE_PLAN=true` (+ Slack/report env) for laptop demo without Checkout (`docs/demo-readiness.md`)

    - Optional: second-org live Slack workspace install after `POST /admin/tenants` / `scripts/second_org_smoke.py` (`docs/demo-readiness.md`)

    - Optional: apply `alembic upgrade head` (`e8a1c47b3d90` plan-and-execute tables; prior: invites / plan_source / billing provider ids) then live `/signup` + `/invite` + admin plan override + billing against local API + Next.js

    - Optional: copy `IDENTITY_PROVIDER=credentials` into `web/.env.local` (shared with API; demo default)

- **Active sprint folder:** `Sprints/Sprint 47/`
