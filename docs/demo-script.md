# Demo script (one organisation)

Spoken / walkthrough path for **Milestone DoD** on the demo tenant. Operator bring-up: `docs/operator.md`. Hardening flags: `docs/demo-readiness.md`.

**Actors:** Org admin (`admin@example.com`) · Platform owner (`owner@example.com`) · Team member (Slack).

**Prep (before the room):** Compose up, migrations, seed, API + web + worker (+ Beat). Prefer `DEMO_ACTIVATE_PLAN=true` if Stripe is not live yet. Tunnel + Slack app + Stripe webhooks when showing live Events/Checkout.

---

## 1. Pay / manage plan

**Surface:** `/app/billing`

1. Sign in as org admin.
2. Show plan status + entitlements.
3. **Live:** Checkout → webhook → `plan_status=active`. **Fallback:** seed with `DEMO_ACTIVATE_PLAN=true` (call out that production uses Stripe).
4. Optional: Customer Portal manage/cancel story.

**Say:** “Billing is per organisation; unpaid orgs cannot run the agent or sync jobs.”

---

## 2. Configure the agent

**Surface:** `/app/agent`

1. Open agent settings (name, prompts / channel allowlist as implemented).
2. Save a small change; confirm it persists.

**Say:** “Each client has isolated agent config — no shared prompts across tenants.”

---

## 3. Knowledge + sync

**Surface:** `/app/knowledge`, `/app/slack`

1. Show Slack connect / install status (or fixture install).
2. Trigger or show last sync status (success / failure banners on `/app`).
3. Optional: upload a small CSV/PDF via knowledge UI.

**Say:** “History and docs land in Qdrant with a hard `client_id` filter.”

---

## 4. Slack Q&A (grounded)

**Surface:** Slack mention or DM

1. Ask a question that exists in the demo corpus (or seeded sample).
2. Show citation / grounded reply (or stub compose if no `ANTHROPIC_API_KEY`).

**Fallback:** `POST /agent/dry-run` or `scripts/agent_dry_run.py --client-id 11111111-…`.

**Say:** “Team members stay in Slack; the org never leaves their workspace for day-to-day Q&A.”

---

## 5. Meeting brief

**Surface:** Slack (brief / agenda intent) or MCP Inspector

1. Ask for a meeting brief on a known topic.
2. Show structured sections from retrieved evidence.

**Say:** “Briefs are tool-backed (MCP) and tenant-scoped.”

---

## 6. Recurring report

**Surface:** Slack channel + `/app` or jobs API

1. Ensure report schedule has a `channel_id` (`DEMO_REPORT_CHANNEL_ID` or portal/API patch).
2. Force post: `POST /jobs/recurring-report` (or wait for Beat).
3. Show digest in channel.

**Say:** “Scheduled digests post into the client’s channel — not a shared inbox.”

---

## 7. Usage / logs

**Surface:** `/app/usage`

1. Show usage summary / recent events / jobs.
2. Point at rate limits and budgets (`docs/governance.md`).

**Say:** “Org reps can see consumption without opening the database.”

---

## 8. Platform admin oversight

**Surface:** `/admin/tenants`, `/admin/health` (owner login)

1. List tenants; open demo org detail (plan, Slack, sync freshness).
2. Optional: suspend / budget override + audit log.
3. Health overview (Compose probes + error rates).

**Say:** “Platform owner oversees without diving into Postgres.”

---

## 9. Isolation note

**Surface:** narrative + optional second-org smoke

1. State: Qdrant filter is fail-closed on `client_id`.
2. Optional: create a second org from `/admin/tenants` (or `scripts/second_org_smoke.py`) and show both rows.
3. Optional: `uv run python scripts/second_org_smoke.py` or `scripts/qdrant_isolation_smoke.py`.

**Say:** “Client B never sees Client A’s knowledge — that’s the product boundary.”

---

## 10. Onboarding stub

**Surface:** Slack “start onboarding” or MCP `start_onboarding`

1. Show the honest **not configured** response (no invented checklist).

**Say:** “Onboarding process is explicitly deferred — we don’t fake a workflow.”

Docs: `docs/onboarding.md`.

---

## Checklist (DoD)

| Beat | Done |
| ---- | ---- |
| Pay / plan visible | ☐ |
| Agent config | ☐ |
| Slack Q&A grounded | ☐ |
| Brief | ☐ |
| Report in channel | ☐ |
| Usage logs | ☐ |
| Admin oversight | ☐ |
| Isolation called out | ☐ |
| Onboarding stub honest | ☐ |

## Needs human (live path)

- Stripe test keys + webhook URL  
- Slack app credentials + tunnel + install  
- Optional `ANTHROPIC_API_KEY` for non-stub compose  
- Report channel id + worker/Beat running  

Without those, narrate with `DEMO_ACTIVATE_PLAN`, dry-run, and portal/admin UIs still on the demo tenant.
