# Task 33.4 — Compose isolation + tests

## Steps

- [x] Compose / graph / policy must not import Anthropic, Claude, OpenAI, or Ollama by name
- [x] Lazy-import Anthropic SDK inside adapter so stub-only imports stay light
- [x] Soften leftover vendor nicknames in graph-adjacent docs (e.g. Sonnet escalation)
- [x] Offline stub path covered
- [x] Anthropic adapter path covered (factory + mocked complete)
- [x] Ollama / recorded HTTP path covered
- [x] Existing grounded-reply tests green
- [x] Isolation regression test (source scan of compose / graph / policy)

## Acceptance criteria

- [x] Compose / graph / policy have no vendor-name imports or identifiers
- [x] Stub + Anthropic + Ollama (recorded HTTP) coverage green
- [x] Grounded-reply / graph suites still pass
- [x] Switching chat backend remains an env change; graph asks for `fast` / `capable` only
