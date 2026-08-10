# Task 13.4 — Guardrails

## Steps

- [x] Harden hedge when retrieval returns no tenant-scoped evidence (deterministic message)
- [x] Never drop `client_id` / tenant filter across route → retrieve → compose
- [x] Defense-in-depth: drop foreign-tenant chunks even if search misbehaves
- [x] Min relevance score (`AGENT_MIN_SCORE`) so weak neighbors still hedge
- [x] Light tests for hedge + tenant filter preservation
- [x] CLI/API dry-run grounded answer for one tenant (sprint exit)
- [x] Docs update

## Acceptance criteria

- [x] No evidence / weak scores → hedged answer (no invented facts; no LLM call)
- [x] Tenant filter / `client_id` required and preserved end-to-end
- [x] Sprint 13 exit: dry-run answers a grounded question for one tenant
