# Changelog

## 0.4.2 — not released yet

**New**

* **Choose the pages of a PDF to index.** A "PDF pages to index" box appears
  when a PDF is chosen: type PDF page numbers (1 = the PDF's first page, as your
  PDF reader shows them), such as 9–880 or 9–14, 21–880, to leave out the title
  page, contents, endorsements and other front or back matter. The box shows
  which printed pages the range covers (or the log does, after the scan, when
  the PDF has no page labels), and the range is kept for that PDF. A paragraph
  or note that runs on into the range is still read where it continues. The book's
  own index was already left out. On the command line: `--pages 9-880`.

**Fixed**

* **PDFs set in two columns** are read column by column. Before, Indicat read
  each line straight across both columns, so a reference could take its book
  from the other column ("Ps 85:1–3; cf. Rom 5:1" beside "85:4–7" gave an
  impossible "Romans 85:4–7"), notes were filed under the wrong page, and the
  contexts mixed the two columns. Paragraphs now run on from one column to the
  next; footnotes across the page are read as before.
* Printer's marks are left out: text outside the PDF's trim (or bleed) box, such
  as the slug line ("….indd 880  11/21/24"), is ignored, so the running foot
  above it is recognized again instead of being read as part of a note.

## 0.4.1 — 2026-10-14

**New**

* **Install updates in place.** When a newer version is out, Indicat offers to
  download it into the same folder as the version you're running, checks that
  it arrived intact, and offers to start it. If that folder can't be written to,
  it goes to your Downloads folder instead. The program now carries its version
  in its name ("Indicat 0.4.1.exe"), so a new version never overwrites the
  running one.
* At its first start, a new version offers to **delete the older copies** in its
  folder and to point desktop, Start menu and taskbar shortcuts to itself.
* **A template for Word indexes made from a PDF** (Edit > Preferences): Word's
  Normal template by default, another template of your choice, or Indicat's
  plain style. The index takes the template's page size, margins and styles;
  Indicat's settings (columns, right-aligned page numbers and leader, index
  font) still apply.

**Fixed**

* "Right-aligned, no leader" could come out with a dot leader in Word: Word
  gave the rebuilt index its own leader (dots) over Indicat's index styles. The
  index now keeps the leader you chose, also in static copies.
* The indexed copy turns off "Automatically update document styles", which let
  the document's template replace Indicat's index styles when Word opened it
  (your original document is not changed).

**Changed**

* Releases no longer include "Indicat for InDesign.jsx"; make the script from
  the app (Tools > Export InDesign script), with your settings. The release
  build still checks that Indicat writes it.

## 0.4.0 — 2026-10-12

**New**

* **Index a PDF.** Choose a PDF (born digital, or OCR'd) and Indicat writes a
  finished index from its printed page numbers, as Word (.docx) or OpenDocument
  (.odt). It finds folios, running heads, footnotes (with note numbers, "143n12"),
  endnotes, note marks and headings from the layout; joins words hyphenated at
  line ends when they are book names or terms, and flags words broken across a
  page ("Deu-‖143‖teronomy"); reads older styles ("Matt. v. 3", "ch. iii. ver.
  4"); reads common OCR slips and flags them; lists pages with missing, thin or
  garbled text; leaves out the book's own index. **Open PDF at this page** opens
  the right page in Acrobat, SumatraPDF, Foxit, Edge, Chrome or Firefox.
* **Guided build (Philosopher Mode).** A step-by-step walk through the index
  settings, offered on first run and in the Help menu.
* **Dictionary forms for Greek and Hebrew.** Words are filed under their lemma
  (λόγου → λόγος, וְהָאָרֶץ → אֶרֶץ), from MorphGNT and the Open Scriptures Hebrew
  Bible; optional subentries for the printed forms; unclear unpointed forms are
  flagged.
* **Review list:** every column sorts (Entry in Bible order), with Reading order
  to go back; **How found** and **Where** filters combine with the others;
  "Chapter only" and "Open-ended (ff)" views.
* **Progress bar** with percentage and a clock; "Index built in X min Y s".
* **Options for each book:** index whole chapters; index the bibliography
  (found by its heading or style; skipped entries listed in grey); verses in
  Hebrew numbering marked [MT] or left out; index font matching the body text.
  Indicat starts with the settings you used last.
* **Menus:** Index (settings for this book) and Edit > Preferences (where results
  are saved — same folder, a fixed folder, or ask — Word, PDF reader, updates,
  abbreviations, books, sections, word indexes, term sets).

**Scripture references**

* An unknown word or abbreviation before a reference is never filled in from
  context: the row is grey with a suggestion ("Ex. → Exodus? (from CMOS shorter,
  switched off)").
* The Apocrypha is always recognized; "Index the Apocrypha" decides whether it is
  indexed. New forms: Mac/Macc, Letter J, WS (flagged), Wisd; 3–4 Kings and
  1–2 Paralipomenon flagged as Vulgate names; Apocalypse.
* "Matthew uses… (16:21)" sets the book; "Zechariah responds… (1:20)" doesn't.
* Short ranges (16–7 = 16–17); impossible verses flagged (verse counts for the
  whole Bible, English and Hebrew numbering); "f" = the next verse (flagged at a
  chapter's end); "ff" kept, sorted after 34 and before 34–35, and marked blue.
* Hebrew (MT) numbering: "Mal 3:23 [4:5]", "51:3 in the MT".
* Italic titles after an author's name, volume:page after an italic title, and
  references in an italic cf. list are told apart.
* "verse 23" after a range of chapters is flagged; every heading level starts a
  new context.

**Word output**

* Note page numbers in term and word indexes are right for notes that run onto
  the next page, for endnotes, and for an entry twice in one note.
* See / See also follow Chicago style in the finished index ("favor. *See*
  grace"; several targets in alphabetical order, separated by semicolons); "See"
  is italic in the live index too.
* The index uses the body text's font, with a warning if that font isn't
  installed (the test kit no longer lands in Helvetica Neue).
* The CSV proof list has a "note" column (merged-note warnings included).
* Term set names lose "(CSV UTF-8)" and the like; a CSV saved in Excel's plain
  format (Greek and Hebrew turned to ????) is warned about.

**Greek skip list:** personal pronouns, τίς/τί and the forms of εἰμί added
(also to saved lists); elided forms (δι’, κατ’, καθ’…) count as the full word.

**InDesign:** fixed the crash on a paragraph with no references ("undefined is
not an object"), and errors now say which step failed. The script has all the
Scripture fixes above, dictionary forms, the bibliography, and Chicago-style
cross-reference settings.

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
