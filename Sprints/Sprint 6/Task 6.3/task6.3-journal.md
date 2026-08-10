# Task 6.3 journal

## Status

`completed`

## Summary

Isolation smoke upserts one raw vector each for tenants A/B, searches each, asserts no cross-tenant hits, and confirms fail-closed on missing `client_id`. Script also probes TEI embed. Sprint 6 exit met.

## Acceptance criteria checklist

- [x] A only sees A — done
- [x] B only sees B — done
- [x] Missing `client_id` fail-closed — done

## Decision log

- Raw orthogonal unit vectors for isolation math (exit: “raw vectors”); TEI probe is additive.
- Smoke script: `scripts/qdrant_isolation_smoke.py`.

## Needs human

None for this task. (Sprint 4 Slack live verify still open at project level.)

## Files changed

- `scripts/qdrant_isolation_smoke.py`
- `docs/qdrant-tei.md`, `README.md`

## Resume notes

Sprint 6 exit met. Next: **Continue Sprint 7 from Task 7.1**.

## Open questions

None.

## Smoke test results

```
collection=knowledge dim=384
tei_embed_ok dim=384
fail_closed_ok missing_client_id
isolation_smoke_ok
```
