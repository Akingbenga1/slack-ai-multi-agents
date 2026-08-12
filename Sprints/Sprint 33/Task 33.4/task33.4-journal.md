# Task 33.4 journal

## Status

`completed`

## Summary

Locked compose / graph / policy behind the `ChatModel` + `fast`/`capable` boundary: no vendor names in those modules; Anthropic SDK is lazy-imported inside the adapter; added isolation + Anthropic mocked-complete coverage. Full `tests/agent/` suite green (114). Sprint 33 exit met.

## Acceptance criteria checklist

- [x] Compose / graph / policy have no vendor-name imports or identifiers
- [x] Stub + Anthropic + Ollama (recorded HTTP) coverage green
- [x] Grounded-reply / graph suites still pass
- [x] Switching chat backend remains an env change; graph asks for `fast` / `capable` only

## Decision log

- **Strategy + Adapter isolation:** product surface (compose/graph/policy) scanned for vendor tokens; adapters + factory remain the only place that name Anthropic/Ollama/OpenAI.
- **Lazy `import anthropic`** inside `AnthropicChatModel.__init__` (optional inject `client=` for tests) — mirrors Ollama’s injectable HTTP client; stub path does not load the SDK at module import.
- Marked LLM provider + model-tier gaps **Implemented (Sprint 33)** in `review.md`.

## Needs human

Optional live compose: `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`, or `LLM_PROVIDER=ollama` + local Ollama (`docs/agent.md`). Offline dry-runs use `LLM_PROVIDER=stub`.

## Files changed

- `api/app/agent/llm.py` (lazy Anthropic import; injectable client)
- `api/app/agent/policy.py`, `run.py` (vendor-neutral wording)
- `tests/agent/test_compose_isolation.py` (new)
- `tests/agent/test_llm_factory.py` (Anthropic complete mock)
- `docs/agent.md`, `Project-Documents/review.md`
- `Sprints/Sprint 33/Task 33.4/task33.4.md`

## Resume notes

**Sprint 33 complete.** Next Ralph batch: **Continue Sprint 34 from Task 34.1** — `PaymentProvider` + Stripe adapter.

## Open questions

None.

## Smoke test results

- `uv run pytest tests/agent/test_compose_isolation.py tests/agent/test_llm_factory.py tests/agent/test_graph.py tests/agent/test_usage_policy.py` → 18 passed
- `uv run pytest tests/agent/` → 114 passed
