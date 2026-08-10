# Task 23.4 — Slack file rename action

Stories: `TM-19`, `TM-23` · Journey: `J10`

## Steps

- [x] In-process (+ MCP) tool: rename Slack file or stored org copy
- [x] Parse requested new name from the ask; fail-closed on `client_id`
- [x] Prefer renaming tenant-stored copy (Slack has no reliable filename rename API)
- [x] Best-effort Slack `files.edit` title update when token/scopes allow
- [x] Document scopes + reinstall need
- [x] Success/failure confirmation in-thread
- [x] Wire `file_rename` (and J10 PDF+rename) in `agent_reply`
- [x] Record `file_rename` usage

## Acceptance criteria

- [x] Rename request produces a clear success or failure message (`TM-23`)
- [x] Org copy under `data/uploads/{client_id}/` is renamed when present
- [x] Slack title update attempted when possible; insufficiency documented
- [x] Scopes documented; Needs-human for app reinstall
- [x] Combined PDF+rename ask still renames after PDF export (`J10`)
