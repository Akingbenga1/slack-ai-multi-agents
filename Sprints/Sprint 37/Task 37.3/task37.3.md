# Task 37.3 — `PdfRenderer` + fpdf2 adapter

**Source:** `Project-Documents/jira-task.md` · `review.md` architecture gap — PDF-renderer

## Steps

- [x] Define `PdfRenderer` Strategy: `title + body → PDF bytes`
- [x] Implement fpdf2 Adapter (owns `fpdf` / `FPDF`)
- [x] Keep `analysis_to_pdf_bytes` as the product facade; move fpdf2 out of it
- [x] `PdfUploadStrategy` / file PDF path call the facade (not fpdf2 by name)
- [x] No `PDF_RENDERER` factory/env unless a second renderer is selected (fpdf2-only this sprint)
- [x] Light smoke: facade still produces PDF bytes without importing fpdf2 in product callers

## Acceptance criteria

- [x] File-PDF export knows only “title + body → PDF bytes”
- [x] fpdf2 is confined to the adapter; product facade remains
- [x] No PDF factory/env key this sprint (single renderer)
