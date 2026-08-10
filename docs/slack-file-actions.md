# Slack file actions (Sprint 23)

Deferred / post-MVP: attach → analyse → PDF deliverable → rename (`J10`, `TM-17`–`TM-19`, `TM-23`).

## Flow

1. Mention/DM with `files` (or file permalink / `F…` id in text)
2. `intake_attachments` downloads via bot token, stores under `data/uploads/{client_id}/`, parses with `extract_document`
3. Agent state carries `attached_evidence`; tools merge attachment chunks ahead of optional RAG
4. Route classifies `file_analyse` / `file_pdf_export` / `file_rename`
5. Heavy workflows (`file_pdf_export`, `file_rename`) also check **jobs** budget before the graph
6. `file_pdf_export`: compose analysis → **fpdf2** PDF → `files.upload` → confirmation in reply
7. `file_rename` (or J10 PDF+rename ask): rename **org-stored copy** (primary) + best-effort Slack **title** via `files.edit` → confirmation in reply

## Rename behaviour (Task 23.4)

Slack has **no reliable API to change a file’s underlying filename**. This stack:

| Step | What happens |
| ---- | ------------ |
| Org copy | Rename under `data/uploads/{client_id}/` (fail-closed path escape / wrong tenant) |
| Slack | Best-effort `files.edit` **title** update (`files:write`) |
| MCP | `rename_slack_file` — same semantics; `client_id` required |

If Slack title edit fails, the reply still confirms the org-copy rename and explains the limitation (`TM-23`).

## PDF library

**fpdf2** — lightweight PDF writer. Documented here so operators know why it appears in `pyproject.toml`. Unicode outside Latin-1 is replaced for Helvetica core fonts (demo-safe).

## Scopes (Needs human)

Add to the Slack app and **reinstall** so tokens pick them up:

| Scope | Why |
| ----- | --- |
| `files:read` | Download attached / referenced files |
| `files:write` | Upload PDF deliverables; `files.edit` title updates for rename |

Install URL still: `{PUBLIC_BASE_URL}/slack/install?tenant_id=…`

## Modules

| Path | Role |
| ---- | ---- |
| `api/app/slack/attachments.py` | Detect refs, download, store, parse |
| `api/app/slack/pdf_export.py` | Analysis text → PDF bytes |
| `api/app/slack/file_actions.py` | PDF upload + rename + TM-23 copy |
| `api/app/slack/client.py` | `files_info`, download, `files_upload`, `files_edit` |
| `api/app/slack/agent_reply.py` | Wires intake + PDF + rename into mention/DM path |
| `mcp_server/tools/rename.py` | MCP `rename_slack_file` |

## Usage events

| `event_type` | When |
| ------------ | ---- |
| `file_job` | Attachment intake ran |
| `pdf_generate` | PDF build/upload attempted |
| `file_rename` | Rename attempted (org copy and/or Slack title) |

These count toward `jobs_daily` (`JOB_BUDGET_EVENT_TYPES`).

## Smoke (offline)

```bash
uv run pytest tests/slack/test_attachments.py tests/slack/test_pdf_export.py tests/slack/test_file_rename.py tests/slack/test_sprint23_smoke.py tests/agent/test_file_route.py -q
```

Live: attach a financial report PDF/CSV in Slack, `@mention` with “produce a PDF of competitor analysis and rename the financial report file to Q3-financial.csv”, confirm PDF + rename confirmation after scopes + reinstall.
