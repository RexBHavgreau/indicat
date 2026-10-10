# Changelog

## 0.3.0 — 2026-10-10

* **Renamed Indicat** (Latin, "it points out"), with a manicule (☞) icon. The
  program is `Indicat.exe`; the InDesign script is "Indicat for InDesign.jsx".
  Created by Beaux Hargrove; free software under the GNU GPL v3 with an
  author-credit term (see NOTICE.md).
* **Settings carry over by themselves.** Indicat finds the settings of
  Scripture Index Builder 0.2 and brings them over the first time it runs; later
  versions read the same settings file. The InDesign script also picks up its
  earlier preferences. Export and import are still available.
* **Original-language word indexes.** Every Greek, Hebrew/Aramaic or Syriac word,
  each in its own index, found by its alphabet. Forms that differ only in
  accents, breathings or vowel points are grouped (switchable). Words to skip
  (articles, conjunctions…) are editable for each index. Quotations are left out:
  paragraphs in a quotation style, indented prose paragraphs, and runs of more
  than four words (adjustable), unless the run is a list of short items
  separated by commas, semicolons or slashes. Tables are read cell by cell.
  Skipped quotations appear as grey rows and in the proofreading list, and can
  be included.
* **Tagged-language word indexes** (Latin, German, French…): the words the
  manuscript marks as that language.
* **Term sets.** Build a set from a text file (one term per line, forms
  separated by |) or a CSV file (heading, subentry, match forms, sort as, see,
  see also). Each set is its own index; options for case, accents, whole words,
  English plurals, Hebrew prefixes and block quotations. Sets are saved and
  exported with the settings, and can be exported back to CSV.
* All indexes are found in the same scan and reviewed in one table (new Index
  column and filter; Edit files a word under another heading). The
  proofreading list covers every index, sorted by page.
* Word: each index gets its own INDEX field and heading; note page numbers are
  completed (33n12) or highlighted in word and term indexes too.
* InDesign: the script builds the same indexes (each as a top-level entry of the
  document's index) with See / See also cross-references; its word and term
  engine is tested to match the app's exactly.
* Output files are now "… - Indexed.docx", "… - Indexed (final).docx" and
  "… - Index Proof List.docx/.csv".
* Command line: `--words greek,hebrew`, `--terms file.csv`, `--no-scripture`.
* Help menu: user guide, Support Indicat, and a new About box.
* Update checking points to github.com/RexBHavgreau/indicat.

## 0.2.0 — 2026-10-10

* **InDesign:** Tools > Export InDesign script (.jsx). The script indexes the open
  document with canonical sort order, handles footnotes, highlights references
  whose book came from context (non-printing condition), and writes an HTML
  and/or CSV proofreading list. Its parser is tested to match the app's exactly.
* **Languages:** Spanish, Portuguese, French, German and Hebrew alongside English,
  chosen from a dropdown that remembers the last choice. Each has its own book
  names, abbreviation sets and reading rules (comma notation, "f./ff.", "s./ss.",
  ordinal words, Hebrew-letter numerals and prefixes).
* **English abbreviations:** SBL, CMOS traditional and CMOS shorter, each
  switchable.
* **Apocrypha** (optional) and **custom books** for anything else a work cites.
* **Index layout:** one index, Old/New Testament, or by section; section order and
  headings set by the user (default OT, Apocrypha, NT, Other); Tanakh order for
  Hebrew (JPS/Koren or BHS).
* **Per-book abbreviation settings**, exportable and importable across versions.
* **Add reference** in the review table.
* **Update check** (active once the project is on GitHub) and a GitHub build
  workflow that runs all tests and publishes releases.
* Fix: in a list like "Sir 24,3 und 1. Mose 1,1", the "1" of a numbered book is no
  longer read as a verse.

## 0.1.2 — 2026-10-10

* New **Make static copy…** path (button, Tools menu, and `static` command): turns a
  checked live index into plain text in a new "(static index)" copy, with note page
  numbers completed (33n12) or highlighted. Detects whether notes were marked bold
  or italic, can optionally update the index first, keeps all index entry fields,
  and never overwrites an existing file.

## 0.1.1 — 2026-10-10

* Note page numbers are now matched to their notes using Word's own finished
  index, not page numbers computed separately. 0.1.0 highlighted many note
  locators it should have completed, mostly from long notes that run onto the
  next page.
* The final-step note options (highlight, automatic n#) now save two copies: one
  with a live index and a "(final)" copy with the plain-text index.
* The note dialog groups its options under "Index stays live" and "Final step".
* "Page Number Separation" dropdown: comma, right-aligned with or without dot
  leader, em/en/word space, em/en dash variants, and a custom separator.
* Clearer label for the Word option; Word now lays out in Print Layout before
  reading pages.

## 0.1.0 — 2026-10-10

First release: .docx scanning with context-aware book resolution, XE fields with canonical \y sort keys, Word-driven pagination, five note-handling modes, page-sorted proofreading list (.docx + .csv), Windows GUI.
