# Onboarding process (stub)

MVP ships an **honest stub** only (Sprint 18). There is no guided checklist,
form collector, or multi-step Slack conversation yet — by design
(`PO-15`, `TM-16`, `deferred:onboarding`).

**This is not tenant signup.** Org reps register at `/signup` (`POST /auth/signup`,
Sprint 31). Slack “start onboarding” / MCP `start_onboarding` is an agent
workflow that always returns *not configured*. It does not create a tenant,
user, or session. See `docs/portal.md`.

## What exists today

| Surface | Behaviour |
| ------- | --------- |
| LangGraph workflow | `onboarding` — route classifies explicit start/process phrasing |
| MCP tool | `start_onboarding(client_id)` → `configured=false` + clear message |
| Agent path | **route → tools → compose**; compose returns the stub text (no LLM, no RAG) |
| Knowledge Q&A | Asks like “onboarding checklist for new hires” stay `qa` → `search_knowledge` |

Shared copy: `mcp_server.tools.onboarding.ONBOARDING_NOT_CONFIGURED_MESSAGE`.

## Extension point (future checklist state machine)

When a real process is designed, extend **without** inventing steps in this
doc. Likely seams:

1. **`start_onboarding`** — flip from stub to “create / resume session” when
   `configured=true` (tenant flag or org portal setting).
2. **New MCP tools** (examples only — not implemented): e.g. `get_onboarding_status`,
   `advance_onboarding_step`, each still requiring `client_id`.
3. **Persistence** — a future `onboarding_sessions` (or similar) table keyed by
   `client_id` + Slack user/channel; store step id, answers, timestamps.
4. **LangGraph** — optional subgraph or tools-node branch that reads session
   state and posts the next prompt; keep compose grounded (no invented policy).
5. **Org portal** — configure checklist templates per tenant (Sprint 19+ UI
   territory once the process is defined).

Do **not** treat the stub message as a product checklist. Do **not** add
placeholder steps “for realism.”

## Verify stub

```bash
# Unit (no Slack / Qdrant)
uv run pytest tests/agent/test_onboarding.py tests/mcp/test_server.py -q -k onboarding

# MCP Inspector (optional)
# npx -y @modelcontextprotocol/inspector uv run python -m mcp_server
# → call start_onboarding with a real tenant client_id
```

Live Slack: mention the bot with “start onboarding” after install + active plan
(see inherited Needs-human items).
