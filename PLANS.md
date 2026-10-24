# Plans

Working list for the next version. A weekly routine ("Indicat weekly build", Saturdays 4:00 AM
Central) builds every item here that is decided and not yet built, tests it, pushes the branch
and runs the Windows build; items with open questions wait for Beaux. Merging and tagging stay
with Beaux.

## 0.4.3

### 1. PDF route: lists of references with roman chapter numbers (built 2026-10-24, on the branch)

**Found on:** an old OCR'd book (2026-10-20). "Heb. iii. 7, ix. 8, x. 15" gives only Hebrews 3:7;
"Matt. v. 3, 9, vi. 9" only Matthew 5:3. The modern form ("Heb. 3:7, 9:8, 10:15") gives all three.

**Decided (2026-10-20):** after an older-style reference (`parser._old_rc`), carry on through a list,
as for modern references: after a comma or semicolon (optionally "and"), another "roman. verse"
("ix. 8", "x. 15–17") is the same book, next chapter; a bare verse (", 9") is the same chapter.
Each item must be exactly a roman numeral, a period and a number, and only right after a
recognized reference. **PDFs only** (older styles are only read in PDFs; Word and the InDesign
script are not changed, so no JS port). Tests in `test_parser.py` (old styles) and `test_pdf.py`:
the two lists above, a semicolon list, a range, and text that must not be taken ("vi. 9" alone
with no reference before it; "see p. 5, iv. 2" after a page number).

**Built:** `parser._old_list` (pattern `old_list`) after an older-style reference; items get the
status "chain" (or the first reference's status, e.g. "check-name" for Vulgate names). The list
stops at anything that isn't "roman. verse" or a bare verse, and where a book name begins
("Cant. ii. 4; 1 Paralip. xvi. 1" stays two references). Tests: `test_parser.test_older_citation_styles`,
`test_pdf.test_old_style_lists`.

## 0.4.2 (released 2026-10-18; see CHANGELOG.md)

### 1. PDF route: two-column pages (built 2026-10-16)

**Found on:** BiblicalMissionsUS textbook (PDF, 2026-10-16). Indicat reads each PDF page line by
line across its whole width (`pdf_io._lines_of` groups characters by baseline only), so on a
page set in two columns, or a PDF exported as two-page spreads, it reads a line of the left
column, then the same line of the right column. Effects in that book:

- References read with the wrong book: "Ps 85:1–3; cf. Rom 5:1" in one column, "85:4–7" in the
  next → "Romans 85:4–7, impossible" (page 880); "vv. 3–4" given to Luke.
- 940 "impossible chapter/verse" and many unindexed "book from context" rows; contexts that mix
  sentences from both columns; page breaks in the middle of lines ("the‖880‖ obedient", 226 rows).
- Notes from later pages filed as "Footnote 4" of page 8, so the review list's page order looks
  wrong (8, 11, 12, 14, then 9).

**Built:** `pdf_io._gutter` finds the strip between the columns (most lines don't cross it,
many have text on both sides); `_keep_whole` leaves lines that cross it and the smaller type
below the columns (footnotes) whole; `_column_order` reads left then right between full-width
lines; `_assemble` runs a paragraph on from the left column to the right. Text outside the trim
(or bleed) box is ignored (printer's marks, slug line), so running feet are found again. On
the 9 sample pages: impossible references 28 → 1 (the book's own "2 Pet 3:14–19"). Spreads (two
pages on one PDF page) are not handled yet.

**Proposed at first:** find the gutter: a vertical strip that no line crosses on most of the page,
then read the left column top to bottom, then the right. A spread (two folios on one PDF page)
becomes two printed pages, each with its own folio. Footnotes are looked for at the foot of each
column. Tests: two-column and spread pages made with reportlab in `test_pdf.py`, plus the real
book once Beaux sends the PDF (or pages 7–14 and 880).

### 2. PDF route: choose the pages to index (built 2026-10-17)

**Wanted:** index only part of a PDF (a chapter, the body without the front or back matter).
Not built before 2026-10-16: it isn't in the code, on any branch, or in an issue.

**Decided (2026-10-16):**

- PDFs only (a Word manuscript has no pages until Word lays it out).
- A "Pages" box next to the PDF, blank for the whole book. It takes **PDF page numbers**
  (1 = the PDF's first page, as a PDF reader shows them), because every page has one, they
  never repeat, and they don't depend on Indicat reading the folios: unnumbered front matter
  (title, copyright, endorsements) and roman pages can be chosen as easily as the rest.
- Several ranges allowed: "9–14, 21–880".
- Indicat echoes the printed pages the range covers ("PDF pages 9–880 = printed xi–862"), so a
  wrong number shows before the scan.
- Pages outside the range aren't scanned; a paragraph or note that runs on into the range from
  the page before is still read where it continues. The range is kept with the book's settings
  and shown in the log and the proofreading list.
- The book's own index is already left out (found by its heading), so the range is mainly for
  front matter and other back matter.

**Built:** `pdf_index.parse_pages` / `describe_pages` / `pdf_info`; `scan_pdf(pages=…)` still reads
every page (folios, running heads, notes that run on) and keeps only the hits on the chosen
pages; the range is kept per PDF in the `pdf_pages` setting (settings version 6). The window's
"PDF pages to index" box echoes the printed pages at once when the PDF has page labels;
otherwise the log gives them after the scan (folios are only known once the PDF is read).
`--pages` on the command line. Not added to the guided build.

## 0.4.1 (released; see CHANGELOG.md)

All items below are built and tested here; what still needs real Word, InDesign and
Windows is listed in CLAUDE.md under "Not yet checked". Built as planned, except: in item 4,
index 3 got no change (Indicat never writes a third level), and the leader is taken from the
'index 1' style, so it also holds for static copies.

### 1. Update in place

**Now:** Help > Check for updates (and the check at start-up) reads the latest GitHub release
and offers to open the download page in the browser. The user downloads `Indicat.exe` by hand.

**Wanted (decided):**

- The .exe carries its version in its name: `Indicat 0.4.1.exe`. A new version never has to
  overwrite the running one.
- The check at start-up (and Help > Check for updates) offers: "Indicat X is available (you
  have Y). Install it in the same folder?" with the release notes. Buttons: Install / Open the
  download page / Not now.
- Install downloads `Indicat X.exe` into the folder the running copy is in, with the progress
  bar, checks the size and the SHA-256 digest GitHub gives for the file (deletes it and says
  so if they don't match), then offers to start the new version and close this one.
- The .jsx is not downloaded.

Fall-backs, each with a plain message; the running copy is never touched:

- Folder not writable (e.g. under Program Files): save to Downloads and open that folder.
- Running from source (`python run_app.py`), not the .exe: open the download page as now.
- No connection, download cut off, digest mismatch: nothing is kept.

Settings carry over as before (`%APPDATA%\Indicat`).

Code: `updates.py` (find the `Indicat *.exe` asset, download, verify), `gui.py`
`_check_updates` (dialog, progress, start the new copy), `build.yml` and `build_exe.bat`
(`--name "Indicat X.Y.Z"`, read from `__init__.py`; the data-file check follows the new name).
Tests against a fake release served locally: find, download, verify, the fall-backs.

Note: 0.4.0 still only opens the download page; the in-place install starts with updates
*from* 0.4.1 onward.

Can't be tested here: the real download and restart on Windows, and SmartScreen/antivirus on a
freshly downloaded unsigned .exe. Needs a run on Beaux's machine (0.4.1 updating to a test
release).

**First start of the new version (decided):**

- It looks in its own folder for older copies (`Indicat 0.4.1.exe`, …, and the old
  `Indicat.exe`) and offers: "Delete the old version (Indicat Y)? Your settings are kept."
  If the old copy is still closing, it waits a moment and tries again; if it can't delete it,
  it says so and leaves it.
- It updates shortcuts that point to the old copy so they open the new one: the desktop, the
  Start menu and the taskbar pins (all `.lnk` files, changed through Windows' own shortcut
  object, which the .exe already carries via pywin32). Shortcuts pointing elsewhere are left
  alone.
- No "Don't remind me about this version" for now; maybe later, once things settle.

Can't be tested here: whether Windows refreshes a retargeted taskbar pin at once or only after
signing out (check on Beaux's machine).

### 2. Stop publishing the InDesign script in the release

The build still writes `Indicat for InDesign.jsx` as a check that Indicat generates a correct
script, but the release no longer carries it (users make their own from the app). In
`build.yml`: write it outside `dist/` (or drop it before publishing) so `files: dist/*` only
publishes the .exe.

### 3. A template for PDF indexes

**Now:** the PDF route writes its .docx index from python-docx's built-in blank document, with
Indicat's own styles (font from the PDF, 10 pt, index 1/2). It ignores the user's Word
templates, so the index doesn't look like the house style.

**Wanted:** Edit > Preferences > "Template for indexes made from a PDF": a .dotx/.dotm/.docx the
user picks. Indicat starts the index from that file: its page size, margins, Normal, Heading and
index 1/2/3 styles. Applies to the .docx output (the .odt keeps Indicat's own styles).

Code: `static_index.write_docx` opens the template instead of `Document()` (a .dotx/.dotm needs
its main content type switched to a document; body text and macros are dropped), and creates a
style only when the template lacks it; a new `pdf_template` setting (bump `SETTINGS_VERSION`,
step in `migrate()`). Tests with a sample template: styles, page size and margins carried.

**Decided:**

- Default: Word's Normal template (`%APPDATA%\Microsoft\Templates\Normal.dotm`). The user
  can pick another template in Preferences. If Normal.dotm isn't found (no Word on the
  computer), Indicat uses its plain style and says so in the log.
- Indicat's settings win over the template: columns, right-aligned page numbers and leader,
  and the index font ("match the body text" takes the font from the PDF; "the document's index
  styles" keeps the template's font). Everything Indicat has no setting for (sizes, indents,
  spacing, page size, margins, headings) comes from the template.

### 4. Fix: "no leader" came out with a dot leader in Word

**What happens:** Indicat writes the "index 1/2" styles with a right tab and no leader. Then, to
read page numbers, it opens the copy in Word and calls `Indexes(i).Update()`. Word's Index
object has its own `TabLeader` setting, which defaults to dots, and Word applies it when it
rebuilds an index with right-aligned numbers, over the style. That is the most likely cause.
(Two others to rule out: the document's attached template set to "Automatically update
document styles", which copies the template's index styles over Indicat's on opening; and
a third index level, index 3, which Indicat doesn't give a tab at all.)

**Fix:** in `word_com`, before updating each index, set `TabLeader` (none → spaces, dot →
dots) and `RightAlignPageNumbers` from the book's settings; give index 3 the same tab as 1 and
2; and turn off "Automatically update document styles" in the copy (never in the original).
`word_mock_test.py` checks the properties are set.

Can't be tested here: needs a run in real Word, ideally on the document where it happened.
If Word still overrides it after this, the fall-back is a note in the build log ("Your
document's styles set the leader; change it in Word: References > Insert Index > Tab leader").

## Parked: a Mac version (for a contributor with a Mac)

Many designers and editors use Macs, so it's worth doing, but Beaux has no Mac to test on.
What it would take:

- A macOS job in `build.yml` (PyInstaller .app, in a .dmg or .zip).
- Settings in `~/Library/Application Support/Indicat`; Cmd shortcuts; the Mac theme; fonts and
  PDF readers found without the Windows registry; page jumps in Acrobat/Skim (Preview can't).
- Word automation (`word_com.py`) is Windows-only: on the Mac, no note locators (n#), static
  copy or CMOS cross-references in the finished copy. Say so in the app; the live Word index,
  the PDF route, the InDesign script and the proofreading list all work.
- Signing and notarizing (Apple developer account, $99/year), or users must right-click > Open.
- The update-in-place design needs a Mac version (replacing an .app bundle).
- Someone with a Mac to test each release in real Word and InDesign.

## Decided against

- Live .odt indexing (2026-10-13). LibreOffice's own index sorts by the shown text, not Bible
  order; Indicat could drive LibreOffice for page numbers instead, but it would add too much to
  an already large app. LibreOffice users keep exporting to PDF and using the PDF route.
