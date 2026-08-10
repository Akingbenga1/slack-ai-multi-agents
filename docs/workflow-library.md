# Shared workflow library (Sprint 24)

Channel upload → org shared library + copy/edit (`J11`, `TM-20`–`TM-21`).

## Schema

Table `workflow_templates` (Alembic `d4e9a21b8c30`):

| Field | Notes |
| ----- | ----- |
| `tenant_id` | Fail-closed scope (`client_id`) |
| `title`, `original_filename`, `body_text` | Discover + advice grounding |
| `source_slack_file_id` | Slack file id when stored from channel |
| `storage_relative_path` | Under `UPLOAD_DIR/{client_id}/` |
| `content_hash` | SHA-256 of bytes (idempotent shared store) |
| `visibility` | `shared` (library) or `personal` (copy/draft) |
| `parent_id` | Set on copies; shared originals leave null |
| `owner_slack_user_id` | Who may edit a personal draft |
| `version` | Bumps when personal draft body changes |

Partial unique indexes (Postgres): one shared row per tenant+hash and per tenant+Slack file id.

## Storage

- Role `file_role=workflow` (extensions: PDF/DOCX/XLSX/CSV/MD/TXT).
- Optional Qdrant ingest enqueue for document-parseable types after store.
- Library helpers: `api/app/workflows/library.py`.

## Slack intents

| Phrasing | Workflow |
| -------- | -------- |
| store/save this workflow … shared library | `workflow_store` |
| list/show/find workflows | `workflow_list` |
| copy workflow \<uuid\> | `workflow_copy` |
| edit/update my draft … | `workflow_edit` |
| advise how to make this workflow work / operationalise | `workflow_advise` |

Reuse Sprint 23.1 attachment intake for store and advice. Confirmations always include success/failure (`TM-23`). Advice uses attachment text or a stored template id (+ optional RAG); does not hedge generically when file evidence exists (`TM-22`).

## MCP

| Tool | Notes |
| ---- | ----- |
| `get_workflow_template` | Required `client_id` + `template_id`; fail-closed |
| `advise_workflow` | Required `client_id` + `question`; pass `body_text` and/or `template_id` |

## Portal / API

- `GET /workflows` — list (optional `q`, `include_personal_for`)
- `GET /workflows/{id}` — tenant-scoped get
- `POST /workflows/{id}/copy` — personal draft
- `PATCH /workflows/{id}` — edit personal draft (owner only)
- Next.js `/app/workflows`

## Needs human

Live Slack verify still needs Sprint 23 file scopes reinstall (`files:read` / `files:write`) plus an active plan.

## J11 smoke (offline)

```bash
uv run pytest tests/workflows/test_j11_smoke.py -q
```

Covers store → list → colleague copy → file-grounded advice (no live Slack). Combined phrasing (“store … and advise…”) is detected via `question_requests_workflow_advice` so Slack can append an advice summary after the store confirmation.
