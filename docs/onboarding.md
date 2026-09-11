# Onboarding process (stub)

MVP ships an **honest stub** only. There is no guided checklist,
form collector, or multi-step Slack conversation yet — by design
(`PO-15`, `TM-16`, `deferred:onboarding`).

**This is not tenant signup.** Org reps register at `/signup` (`POST /auth/signup`).
MCP `start_onboarding` always returns *not configured*. It does not create a tenant,
user, or session. See `docs/portal.md`.

## What exists today

| Surface | Behaviour |
| ------- | --------- |
| MCP tool | `start_onboarding(client_id)` → `configured=false` + clear message |
| Product agent | Plain-English asks go through the Deep Agents harness; there is no dedicated onboarding classifier |
| Knowledge Q&A | Asks like “onboarding checklist for new hires” are ordinary harness requests (or knowledge tools if registered) |

Shared copy: `mcp_server.tools.onboarding.ONBOARDING_NOT_CONFIGURED_MESSAGE`.

## Extension point (future checklist state machine)

When a real process is designed, extend **without** inventing steps in this
doc. Likely seams:

1. **`start_onboarding`** — flip from stub to “create / resume session” when
   `configured=true` (tenant flag or org portal setting).
2. **New MCP tools** (examples only — not implemented): e.g. `get_onboarding_status`,
   `record_onboarding_answer`.
3. **Harness / Slack delivery** — only if the product needs a distinct delivery
   shape; otherwise keep using the shared `plan_and_execute` entry.

Do not reintroduce a fixed workflow-name classifier for this stub.
