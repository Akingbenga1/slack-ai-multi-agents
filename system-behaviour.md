# System behaviour scenarios — daily office worker operations

Plain-English requests a typical office worker might make in a day.  
Each scenario should be achievable by the agent through English plan steps and real CLI execution (`uvx` or built-in tools).  
Scenarios span common file types and everyday tasks: reading, converting, summarizing, organizing, comparing, and producing outputs.

**5 PDF-focused** scenarios and **20** centred on other everyday office formats (Word, Excel, PowerPoint, images, audio, email, and more).

---

## 1. Summarize a PDF report for email

**User request:** “Summarize this quarterly report PDF into bullet points I can paste into an email.”

---

## 2. Clean up a Word memo with tracked changes

**User request:** “Accept the sensible edits in this Word memo and give me a clean final version without track changes or comments.”

---

## 3. Merge multiple PDFs into one file

**User request:** “Combine these three signed contract PDFs into a single PDF in the same order.”

---

## 4. Extract tables from a PDF invoice

**User request:** “Pull the line items and totals from this PDF invoice into a spreadsheet.”

---

## 5. Clean and deduplicate a CSV contact list

**User request:** “Remove duplicate email addresses from this contact list and sort it alphabetically by last name.”

---

## 6. Filter an Excel expense sheet by date range

**User request:** “From this expenses spreadsheet, keep only rows between 1 March and 31 March and show the total by category.”

---

## 7. Merge three regional CSV sales exports

**User request:** “Combine these three regional sales CSV files into one master spreadsheet sorted by date and customer.”

---

## 8. Summarize meeting notes and action items

**User request:** “Read these meeting notes and give me a short summary plus a numbered list of action items with owners.”

---

## 9. Compare two policy PDFs and highlight differences

**User request:** “Compare last year’s policy PDF with this year’s version and list what changed in plain English.”

---

## 10. Extract text from a scanned PDF (OCR)

**User request:** “This PDF is a scan — extract the text so I can search and copy it.”

---

## 11. Compress images for a presentation handout

**User request:** “These photos are too large for email — resize them to a reasonable width and compress them without changing the filenames.”

---

## 12. Combine screenshots into a shareable image pack

**User request:** “Take these four PNG screenshots and package them as a ZIP with consistent filenames so I can attach them to an email.”

---

## 13. Extract a slide outline from PowerPoint

**User request:** “Pull just the slide titles and main bullet points from this PowerPoint into a plain text outline I can share.”

---

## 14. Pull speaker notes from a presentation

**User request:** “Extract the speaker notes from this PowerPoint into a Word document.”

---

## 15. Unzip an archive and list what is inside

**User request:** “Unzip this folder and give me a list of every file with its size and type.”

---

## 16. Rename receipt photos in batch

**User request:** “Rename all these receipt photos from `IMG_*.jpg` to `2026-03-Receipt-01.jpg`, `2026-03-Receipt-02.jpg`, and so on in date order.”

---

## 17. Validate and pretty-print a JSON config file

**User request:** “Check whether this JSON settings file is valid and rewrite it in a readable indented format.”

---

## 18. Convert Markdown release notes to HTML

**User request:** “Convert these release notes from Markdown to a clean HTML page I can paste into our intranet.”

---

## 19. Write an executive summary from a report and spreadsheet

**User request:** “Using the attached Word report and Excel numbers, draft a one-page executive summary document I can circulate.”

---

## 20. Redact sensitive information in a Word file before sharing

**User request:** “Before I send this Word document externally, remove or mask all phone numbers and email addresses.”

---

## 21. Split an Excel workbook into separate files by sheet

**User request:** “Split this Excel workbook so each worksheet becomes its own file named after the tab.”

---

## 22. Generate personalised letters from a CSV list

**User request:** “For each row in this CSV, fill the attached Word letter template and save one completed document per person.”

---

## 23. Build a mailing list from vCards and a spreadsheet

**User request:** “From these vCard files and the contact spreadsheet, produce one deduplicated CSV with name, company, email, and phone.”

---

## 24. Transcribe and summarize a recorded meeting

**User request:** “Transcribe this meeting audio and give me a summary with decisions and follow-ups.”

---

## 25. Produce a daily briefing from inbox exports

**User request:** “From these exported `.eml` messages and the attached calendar `.ics` file, write a morning briefing: today’s meetings, urgent threads, and open tasks.”

---

## Coverage matrix (quick reference)

| Category            | Scenarios        |
|---------------------|------------------|
| PDF                 | 1, 3, 4, 9, 10   |
| Word / text         | 2, 8, 14, 19, 20, 22 |
| Excel / CSV         | 5, 6, 7, 21, 23  |
| PowerPoint          | 13, 14           |
| Images              | 11, 12, 16       |
| Archives            | 12, 15           |
| Structured data     | 17, 23           |
| Markdown / HTML     | 18               |
| Audio               | 24               |
| Email / calendar    | 25               |
| Multi-file workflows| 7, 19, 22, 23, 25 |
