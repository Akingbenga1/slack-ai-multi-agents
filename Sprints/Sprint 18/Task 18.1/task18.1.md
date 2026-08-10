# Task 18.1 — Graph/MCP `start_onboarding` stub

## Steps

- [x] Add MCP tool `start_onboarding` that returns a clear “not configured” payload (`client_id` required)
- [x] Add `onboarding` workflow + route classification for explicit start/process phrasing
- [x] Wire tools node → MCP `start_onboarding` (no RAG inventing a process)
- [x] Compose returns the stub message deterministically (no LLM / no generic hedge)
- [x] Light unit tests (MCP + route/agent) + docs pointer

## Acceptance criteria

- [x] Explicit onboarding-start asks classify to `onboarding` (knowledge Q&A about “onboarding checklist” stays `qa`)
- [x] MCP / graph path returns a clear “not configured” message
- [x] No fabricated onboarding checklist or state machine
- [x] Ready for 18.2 extension-point documentation
