# Task 26.3 — Slack files package split + client Adapter

**Sprint:** 26 — Slack delivery Strategies  
**Label:** `pattern-upgrade:slack-delivery`  
**Source:** `Project-Documents/jira-task.md` · `review.md` §5.4 P2

## Steps

- [x] Split `files/refs.py`, `intake.py`, `pdf.py`, `rename.py` + facade `__init__.py`
- [x] Keep `attachments.py` / `file_actions.py` as re-export shims
- [x] Move install/token → client factories to `store.client_for_tenant` / `client_for_team`
- [x] Keep `SlackWebClient` HTTP-only; thin re-exports on `client` for back-compat
- [x] Update sync + docs imports
- [x] Light smoke: full `tests/slack/` suite

## Acceptance criteria

- [x] File helpers are modular; facade usable by delivery Strategies
- [x] Token/install factory lives in store; client is HTTP Adapter
- [x] Existing import paths still work

## Notes

Low-level PDF bytes remain in `pdf_export.py`; upload orchestration is `files/pdf.py`.
