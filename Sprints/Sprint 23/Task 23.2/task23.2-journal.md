# Task 23.2 journal

## Status

`completed`

## Summary

Added file-transform workflows and routing, compose prompts, Sonnet escalation, and a jobs-budget gate (with clear Slack denial copy) before heavy `file_pdf_export` / `file_rename` work.

## Acceptance criteria checklist

- [x] Analyse-from-attachment → `file_analyse`
- [x] PDF competitor analysis → `file_pdf_export`
- [x] Rename → `file_rename`
- [x] Heavy-job denial copy when jobs budget / plan blocks

## Decision log

- Combined J10 “PDF + rename” asks classify to `file_pdf_export` (PDF first); rename note deferred to 23.4
- `has_attachments` heuristic routes vague “this file” asks to `file_analyse`
- Heavy gate reuses `check_budget(..., "jobs")` after agent entitlement

## Needs human

- Same Slack scope reinstall as 23.1 for live verification

## Files changed

- `api/app/agent/nodes/route.py`, `state.py`, `prompts.py`, `policy.py`
- `api/app/slack/agent_reply.py` (`check_file_job_entitlement`)
- `tests/agent/test_file_route.py`
- `docs/agent.md`

## Resume notes

Task 23.3 implements PDF generation + upload on `file_pdf_export`.

## Open questions

- None
