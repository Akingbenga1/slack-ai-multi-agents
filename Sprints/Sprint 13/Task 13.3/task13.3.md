# Task 13.3 — Haiku / Sonnet policy

## Steps

- [x] Default model tier Haiku; escalate on complexity flags
- [x] Settings for Haiku / Sonnet model ids
- [x] Route node applies policy; compose uses `model_tier`
- [x] Record `llm_tokens` usage (units = input+output) toward budgets
- [x] Light tests for escalation + usage recording

## Acceptance criteria

- [x] Simple QA uses Haiku (or stub-haiku)
- [x] Complexity / summarize-status paths escalate to Sonnet
- [x] Token usage counted in `usage_events`
