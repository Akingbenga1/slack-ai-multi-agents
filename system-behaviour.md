# System behaviour scenarios — daily office worker operations

Plain-English requests a typical office worker might make in a day.  
Each scenario should be achievable by the agent through English plan steps and real CLI execution (`uvx` or built-in tools).  
Scenarios span common file types and everyday tasks: reading, converting, summarizing, organizing, comparing, and producing outputs.

This set is **50** operations, one notch more involved than the previous list: most requests combine two related outcomes (extract then compose, batch plus a short report, or two inputs into one deliverable). They stay within ordinary office work — not specialist or multi-day programmes.

The previous set of scenarios is preserved in `system-behaviour-old.md`; the operations below are deliberately distinct from those.

---

## 1. Pull matching pages from a long PDF into a packet

**User request:** “From this long PDF, copy every page that mentions the project name into a new PDF packet, and give me a one-page list of which original page numbers you included.”

---

## 2. Add a cover sheet and renumber a report pack

**User request:** “Put this cover-page PDF in front of the report, then number the whole pack continuously starting at 1, including the cover.”

---

## 3. Convert a PDF report to an editable Word file

**User request:** “Turn this PDF report into a Word document I can edit, keeping the headings and the order of the sections.”

---

## 4. Harvest links from a PDF into a spreadsheet

**User request:** “List every hyperlink in this PDF in a spreadsheet with the page number, the visible text, and the URL.”

---

## 5. Stamp a routing banner on several PDFs

**User request:** “On the first page of each of these PDFs, add a banner that says ‘Copy for Finance — do not circulate’, and keep the rest of the pages unchanged.”

---

## 6. Split a scan into one PDF per invoice

**User request:** “This scan is several invoices in one PDF, separated by blank pages — split it into one PDF per invoice and name them Invoice-01, Invoice-02, and so on.”

---

## 7. Export PDF highlights into a comment log

**User request:** “Pull the highlighted passages and sticky notes from this PDF into a spreadsheet with page number, type, and the text.”

---

## 8. Make a greyscale print copy of a colour PDF

**User request:** “Make a greyscale copy of this colour PDF for cheaper printing, and tell me the original and new file sizes.”

---

## 9. Place a signature image on a marked contract page

**User request:** “Put this signature PNG in the bottom-right of page 4 of the contract PDF, and save a new signed copy without changing the original.”

---

## 10. Build a numbered pack with a contents page

**User request:** “These PDFs need to go out as one pack — make a contents page listing each filename in order, then combine that page with the files behind it.”

---

## 11. Extract figures from a Word report into a folder

**User request:** “Pull every image out of this Word report into a figures folder named Figure-01, Figure-02, and so on, and give me a short index of caption text if the document has captions.”

---

## 12. Turn a Word SOP into a checklist spreadsheet

**User request:** “Convert this numbered Word procedure into a spreadsheet with one row per step: step number, instruction, and an empty Done column.”

---

## 13. Compare two Word drafts by section

**User request:** “Compare this week’s Word draft with last week’s and give me a table of section titles where the text changed, with a short note on what changed.”

---

## 14. Apply house header and footer across several Word files

**User request:** “Add our standard header (document title) and footer (Page X of Y plus the date) to all these Word files, and list any file that already had a different header.”

---

## 15. Turn an interview transcript into a Q&A table

**User request:** “This Word transcript marks questions in bold — turn it into a two-column table of question and answer, one row per exchange.”

---

## 16. Build a glossary from bold terms in a handbook

**User request:** “Collect every bold term in this Word handbook into a glossary document, alphabetised, with the page or heading where it first appears.”

---

## 17. Combine several sets of minutes into one running log

**User request:** “Merge these weekly Word minutes into one running log, with a date heading before each week’s notes, in date order.”

---

## 18. Export a Word file to PDF and to plain text

**User request:** “Save this Word document as both a PDF and a plain-text file, using the document title as the filename for both.”

---

## 19. Fill missing prices from a price list

**User request:** “This order sheet is missing unit prices — look them up from the price-list workbook by product code, fill the blanks, and list any codes you could not find.”

---

## 20. Split a timesheet by person and add a totals file

**User request:** “Split this timesheet into one spreadsheet per employee, and also make a totals file with hours per person.”

---

## 21. Normalise mixed dates and report failures

**User request:** “These date columns are a mix of formats — convert them all to YYYY-MM-DD and give me a list of rows you could not parse.”

---

## 22. Join two lists and write the exceptions

**User request:** “Join the staff list and the access-request list on employee ID into one spreadsheet, and put unmatched IDs from either side on an Exceptions sheet.”

---

## 23. Add budget variance and flag overspend

**User request:** “From this budget-versus-actual sheet, add a variance column and a percent-over column, and highlight any row more than 10% over budget.”

---

## 24. Break a survey export into one sheet per question

**User request:** “This survey export has one row per response — make a workbook with one sheet per question showing each answer and how many times it appears.”

---

## 25. Format a CSV as a usable Excel workbook

**User request:** “Turn this CSV into an Excel file with a frozen header row, autofilter on, and currency format on every money column.”

---

## 26. Copy this week’s rows into a named snapshot sheet

**User request:** “From this running log, copy only this week’s rows into a new sheet named for the week-ending date, and leave the original sheet as it is.”

---

## 27. Deduplicate a product list keeping the latest row

**User request:** “This product list has duplicate SKUs — keep the row with the latest date for each SKU, and write the dropped rows to a Removed sheet.”

---

## 28. Build a simple remaining-days table from dates

**User request:** “From this task sheet with start date, end date, and percent complete, add columns for working days remaining and a short On track / At risk flag if less than 20% is left and more than 50% of the time has passed.”

---

## 29. Drop a spreadsheet table onto a named slide

**User request:** “Put the summary table from this spreadsheet onto the slide titled ‘This month’ in the deck, and export that slide as a PNG.”

---

## 30. Extract deck images named by slide number

**User request:** “Pull every image out of this PowerPoint and name them like Slide-03-image-01 so I can see which slide they came from.”

---

## 31. Insert one deck’s section into another after a divider

**User request:** “Copy the slides from the section called ‘Risks’ in this deck into the other deck, placing them immediately after the slide titled ‘Risks — divider’.”

---

## 32. Title-case slide titles and list untitled slides

**User request:** “Make every slide title in this deck Title Case, and give me a list of slide numbers that have no title.”

---

## 33. Export a deck as PNG slides and as one PDF

**User request:** “Export this presentation as one PNG per slide and also as a single PDF, using the same slide order.”

---

## 34. Build a short status deck from a brief and a KPI sheet

**User request:** “Using this Word brief and the KPI spreadsheet, make a five-slide status pack: title, three highlights, and a numbers slide.”

---

## 35. Make a four-up contact sheet PDF from photos

**User request:** “Arrange these four photos on one landscape page in a 2×2 grid with filenames under each, and save it as a PDF.”

---

## 36. Square-crop catalog photos to a fixed size

**User request:** “Crop these product photos to a square, pad with white if needed, and save them all at 1200×1200 pixels for the catalog.”

---

## 37. Convert a mixed image folder to matching JPGs

**User request:** “This folder is a mix of TIFF and PNG — convert everything to JPG with the longest side at 1600 pixels, keeping the original names.”

---

## 38. Caption figures and assemble them into a PDF

**User request:** “Using this caption list, add figure numbers and captions under each image and combine them into one PDF in list order.”

---

## 39. Upright sideways photos and drop camera metadata

**User request:** “Rotate any sideways photos so they are upright, save new copies, and strip camera and location metadata from those copies.”

---

## 40. Copy only reviewable documents into a clean tree

**User request:** “From this mixed dump, copy only Word and PDF files into a Review folder, keeping the same subfolder names, and give me a count by type.”

---

## 41. Prefix filenames with last-modified dates

**User request:** “Rename these files so each one starts with its last-modified date as YYYY-MM-DD_, keeping the rest of the original name.”

---

## 42. List oversized files with path and type

**User request:** “List every file in this folder tree larger than 5 MB, with path, size, and type, sorted largest first.”

---

## 43. Zip a folder excluding drafts and temp files

**User request:** “Zip this project folder for sending, but leave out anything with temp, draft, or original in the name, and include a short contents list in the zip.”

---

## 44. Turn a week of calendar events into a Word agenda

**User request:** “From this calendar file, make a Word agenda for the week grouped by day, with time and location on each line.”

---

## 45. Save email attachments into dated folders

**User request:** “From these saved emails, extract the attachments into folders named by the email date, and give me a list of which email each file came from.”

---

## 46. Make a sign-in sheet from a meeting invite and attendee list

**User request:** “Using this meeting calendar file and the Word attendee list, produce a one-page sign-in sheet PDF with name, organisation, and a signature column.”

---

## 47. Convert voice notes to MP3, even out volume, and zip them

**User request:** “Convert these voice notes to MP3, even out the volume so none is much louder than the others, zip them, and include a contents list with duration.”

---

## 48. Make a short preview clip and a full MP3 from a recording

**User request:** “From this meeting recording, give me a two-minute preview from the start and a full MP3 of the whole file.”

---

## 49. Flatten a nested JSON export into a spreadsheet

**User request:** “This JSON export is nested — flatten it into a spreadsheet with one row per record and dotted column names for the nested fields.”

---

## 50. Turn a Markdown how-to into a Word SOP with a title page

**User request:** “Convert this Markdown how-to into a Word SOP with a title page (title, owner, date) and numbered steps in the body.”

---

## Coverage matrix (quick reference)

| Category             | Scenarios                                      |
| -------------------- | ---------------------------------------------- |
| PDF                  | 1, 2, 3, 5, 6, 7, 8, 9, 10                     |
| Word / text          | 3, 11, 12, 13, 14, 15, 16, 17, 18, 44, 50      |
| Excel / CSV          | 4, 12, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28  |
| PowerPoint           | 29, 30, 31, 32, 33, 34                         |
| Images               | 9, 11, 30, 35, 36, 37, 38, 39                  |
| Files / folders      | 40, 41, 42, 43                                 |
| Structured data      | 49                                             |
| Markdown / HTML      | 50                                             |
| Audio / video        | 47, 48                                         |
| Email / calendar     | 44, 45, 46                                     |
| Batch across files   | 5, 14, 20, 37, 39, 40, 41, 43, 45, 47          |
| Multi-file workflows | 2, 10, 19, 22, 29, 31, 34, 38, 46              |
