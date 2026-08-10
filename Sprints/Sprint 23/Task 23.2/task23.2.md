# Task 23.2 — Intent routing for file-transform workflows

Stories: `TM-23` (denial copy) · Journey: `J10`

## Steps

- [x] Classify asks: analyse-from-attachment, produce PDF deliverable, rename file
- [x] New workflow names: `file_analyse` / `file_pdf_export` / `file_rename`
- [x] Compose prompts for file analyse + PDF export
- [x] Budget/entitlement gate before heavy PDF/file jobs; clear Slack denial copy
- [x] Escalate file workflows to Sonnet via complexity policy

## Acceptance criteria

- [x] “Analyse this attached report…” → `file_analyse`
- [x] “Produce a PDF competitor analysis…” → `file_pdf_export`
- [x] “Rename the file…” → `file_rename`
- [x] Inactive plan / jobs budget exceeded → clear Slack denial before heavy work
