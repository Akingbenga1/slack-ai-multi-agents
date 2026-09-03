# System behaviour scenarios — daily office worker operations

Plain-English requests a typical office worker might make in a day.  
Each scenario should be achievable by the agent through English plan steps and real CLI execution (`uvx` or built-in tools).  
Scenarios span common file types and everyday tasks: reading, converting, summarizing, organizing, comparing, and producing outputs.

**7 PDF-focused** scenarios and **23** centred on other everyday office formats (Word, Excel, PowerPoint, images, audio, email, and more).

The previous set of scenarios is preserved in `system-behaviour-old.md`; the operations below are deliberately distinct from those.

---



## 1. Split a long PDF into one file per section

**User request:** “This 60-page handbook PDF has bookmarks for each section — split it into a separate PDF per section, named after the section.”

---



## 2. Stamp page numbers and a confidentiality footer on a PDF

**User request:** “Add ‘Page X of Y’ and the word ‘Confidential’ to the bottom of every page of this PDF.”

---



## 3. Fill in a PDF application form and flatten it

**User request:** “Use the details in this spreadsheet row to fill in the attached PDF form, then flatten it so the fields can’t be edited.”

---



## 4. Fix rotation and drop blank pages in a scan

**User request:** “Some pages in this scanned PDF are sideways and a few are completely blank — straighten the sideways ones and remove the blanks.”

---



## 5. Shrink an oversized PDF to fit an upload limit

**User request:** “This PDF is 42 MB but the portal only accepts 10 MB — make it smaller while keeping the text readable.”

---



## 6. Extract all embedded images from a PDF

**User request:** “Pull every photo and diagram out of this PDF and save them as separate image files.”

---



## 7. Reorder and delete pages in a PDF

**User request:** “Remove pages 3 and 7 from this PDF and move the appendix at the back to the front.”

---



## 8. Reformat a Word document to house styles

**User request:** “Reformat this Word document to use our heading styles, Arial 11 body text, and 1.15 line spacing throughout.”

---



## 9. Collect all Word comments into a review log

**User request:** “Pull every comment out of this Word document into a table showing who wrote it, which paragraph it points at, and what it says.”

---



## 10. Replace an old company name across many documents

**User request:** “We rebranded — replace the old company name with the new one across all these Word files and tell me how many changes you made per file.”

---



## 11. Split a long Word document by heading

**User request:** “Break this long Word document into one file per top-level heading, named after that heading.”

---



## 12. Check length and readability before publishing

**User request:** “Give me the word count per section of this document and flag any paragraph longer than 60 words or written at too high a reading level.”

---



## 13. Cross-tabulate a flat transaction list

**User request:** “Turn this flat list of transactions into a summary table with months down the side and regions across the top.”

---



## 14. Reconcile a bank export against the ledger

**User request:** “Compare this bank export with our ledger spreadsheet and list the transactions that appear in one but not the other.”

---



## 15. Add calculated VAT and running-total columns

**User request:** “Add a VAT column at 20% and a running total to this spreadsheet, and put the grand total at the bottom.”

---



## 16. Flag data-quality problems in a spreadsheet

**User request:** “Check this spreadsheet for missing required fields, invalid dates, and negative quantities, and give me a list of the rows that need fixing.”

---



## 17. Convert a spreadsheet to JSON for a developer

**User request:** “Our developer needs this product spreadsheet as JSON — one object per row using the column headers as keys.”

---



## 18. Chart monthly revenue as an image

**User request:** “Make a bar chart of monthly revenue from this spreadsheet and save it as a PNG I can drop into a slide.”

---



## 19. Build a slide deck from a written outline

**User request:** “Turn this outline document into a PowerPoint with one slide per heading and the bullets underneath each.”

---



## 20. Update branding and dates across every slide

**User request:** “Swap the old logo for the new one on all slides in this deck and change the footer date to March 2026.”

---



## 21. Export a deck as a printable handout

**User request:** “Turn this presentation into a handout PDF with four slides per page and room for notes.”

---



## 22. Convert phone photos to a usable format

**User request:** “These HEIC photos from my phone won’t open on my colleague’s PC — convert them all to JPG.”

---



## 23. Watermark images before sending them out

**User request:** “Add a faint ‘Draft — Not For Distribution’ watermark across these product images before I share them.”

---



## 24. Strip hidden metadata from photos

**User request:** “Before these photos go on our website, remove the GPS location and camera details embedded in them.”

---



## 25. Find duplicate files across a folder tree

**User request:** “This shared folder has grown out of control — find files that are genuine duplicates of each other and show me which copies I can delete.”

---



## 26. Sort a messy downloads folder

**User request:** “Sort everything in this folder into subfolders by file type and by the month it was created.”

---



## 27. Convert an XML export to a spreadsheet

**User request:** “Our old system exports XML — flatten this export into a CSV with one row per record.”

---



## 28. Turn a saved web page into clean text

**User request:** “I saved this intranet page as HTML — strip out the navigation and styling and give me just the content as Markdown.”

---



## 29. Pull the audio out of a recorded call and split it

**User request:** “Extract the audio from this meeting recording and split it into 15-minute segments so I can share the relevant part.”

---



## 30. Build a calendar file from a schedule spreadsheet

**User request:** “From this spreadsheet of training dates, create a calendar file I can import into Outlook with one event per row.”

---



## Coverage matrix (quick reference)


| Category             | Scenarios                      |
| -------------------- | ------------------------------ |
| PDF                  | 1, 2, 3, 4, 5, 6, 7            |
| Word / text          | 8, 9, 10, 11, 12, 19           |
| Excel / CSV          | 13, 14, 15, 16, 17, 18, 27, 30 |
| PowerPoint           | 19, 20, 21                     |
| Images               | 6, 18, 22, 23, 24              |
| Files / folders      | 25, 26                         |
| Structured data      | 17, 27                         |
| Markdown / HTML      | 28                             |
| Audio / video        | 29                             |
| Email / calendar     | 30                             |
| Batch across files   | 10, 22, 23, 24, 25, 26         |
| Multi-file workflows | 3, 10, 19, 20, 25              |


