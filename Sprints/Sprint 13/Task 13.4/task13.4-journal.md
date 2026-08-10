# Task 13.4 journal

## Status

`completed`

## Summary

Hardened agent guardrails: **hard hedge** (fixed message, no LLM) when there is no tenant-scoped evidence above `AGENT_MIN_SCORE` (default `0.70`); every node requires `client_id` and re-filters foreign chunks. Live dry-run on sample corpus answers a grounded refund question; gibberish hedges.

## Acceptance criteria checklist

- [x] Hedge when no / weak retrieval evidence
- [x] Never drop tenant filter / `client_id`
- [x] Sprint 13 exit: CLI dry-run grounded answer for one tenant

## Decision log

- Hard hedge short-circuits compose (no Anthropic/stub call; `usage_tokens=0`).
- Absolute cosine floor `AGENT_MIN_SCORE=0.70` tuned against bge-small + sample corpus (good ~0.77, junk ~0.62).
- Defense-in-depth filter in retrieve + compose even if search leaks foreign hits.

## Needs human

- Optional: `ANTHROPIC_API_KEY` for non-stub grounded compose (`docs/agent.md`).

## Files changed

- `api/app/agent/guardrails.py`, `nodes/{route,retrieve,compose}.py`, `state.py`, `__init__.py`
- `api/app/settings.py`, `.env.example`
- `tests/agent/test_guardrails.py`, `test_graph.py`
- `docs/agent.md`
- `Sprints/Sprint 13/Task 13.4/*`

## Resume notes

Sprint 13 complete. Next: **Continue Sprint 14 from Task 14.1** (wire mention/DM → LangGraph).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/agent -q  → 19 passed

AGENT_CHECKPOINTER=memory uv run python scripts/agent_dry_run.py \
  --client-id aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa \
  --question "refund policy within 30 days" --memory --no-usage
→ hedge=False chunks=2 grounded stub citing sample_doc.csv

… --question "asdkfjhasdkfjh random gibberish 99999"
→ hedge=True chunks=0 hard hedge message
```
