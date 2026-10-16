# Plans

Working list for the next version. Building starts once the list has a handful of items and
Beaux says go.

## 0.4.2

(nothing yet)

## 0.4.1 (built 2026-10-14; see CHANGELOG.md)

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

### 5. PDF route: two-column pages (added 2026-10-16, built)

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
