# Task 23.5 journal

## Status

`completed`

## Summary

Added isolation + usage + offline J10 smoke tests covering blank `client_id`, cross-tenant org-copy rejection, PDF upload, and rename. Confirmed `file_job` / `pdf_generate` / `file_rename` are in `JOB_BUDGET_EVENT_TYPES`. Live Slack remains Needs-human for scopes/reinstall.

## Acceptance criteria checklist

- [x] Fail-closed isolation on file-action helpers
- [x] Usage event types for file/PDF/rename
- [x] Offline J10 smoke (attach path → PDF → rename)
- [x] Sprint 23 exit offline; live Needs-human only

## Decision log

- Cross-tenant rename returns `ok=False` (does not raise) so Slack reply path stays resilient; isolation still enforced on disk

## Needs human

- Live J10: reinstall app with `files:read` / `files:write`, attach financial report, ask for PDF competitor analysis + rename, confirm in Slack

## Files changed

- `tests/slack/test_sprint23_smoke.py` (new)
- `docs/slack-file-actions.md` (smoke commands)

## Resume notes

Sprint 23 complete (deferred theme). Next: **Continue Sprint 24 from Task 24.1** (shared workflow library) unless product re-prioritises.

## Smoke test results

```bash
uv run pytest tests/slack/test_file_rename.py tests/slack/test_sprint23_smoke.py tests/slack/test_pdf_export.py tests/agent/test_file_route.py -q
```

Offline checks passed this session.

## Commercial mapping

Team-member Slack file I/O (`J10` / `TM-17`–`TM-19`) — post-MVP deferred capability after core agent/RAG/billing milestone.
