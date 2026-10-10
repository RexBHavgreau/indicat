# Scripture Index Builder 0.2.0

Builds a canonically ordered Scripture index for a Word manuscript (.docx), or
for an InDesign document through a generated script, plus a proofreading list of
every indexed reference sorted by page. Languages: English, Spanish, Portuguese,
French, German and Hebrew.

Your original manuscript is never changed. The tool writes:

| File | What it is |
|---|---|
| `<name> - Scripture Index.docx` | A copy of the manuscript with an index entry (XE) field after every reference and the index at the end |
| `<name> - Scripture Index Proof List.docx` | Every indexed reference by page, with context, how its book was found, and a checkbox; then everything found but *not* indexed |
| `<name> - Scripture Index Proof List.csv` | The same data for Excel |

## Build the .exe (once per version)

1. Install Python 3.10 or newer from python.org and tick **Add python.exe to PATH**.
2. Double-click **`build_exe.bat`**. It creates a private environment in `.venv`,
   installs the requirements and PyInstaller, and builds the app.
3. The program is `dist\ScriptureIndexBuilder.exe`. It runs on its own and can be
   copied to any Windows PC. Other users don't need Python.

## Using it

1. Choose the **Language**, the **Index layout** (one index; Old/New Testament;
   or by section: OT, Apocrypha, NT, Other), and whether to **Recognize the
   Apocrypha** (off by default, so "Wisdom" or "Judith" in prose isn't caught).
2. **Browse** to the manuscript and click **Scan**.
2. Review the list:
   * **Yellow rows** took their book from context (e.g. "(5:17)" after "Proverbs 5").
     These are the ones worth a look.
   * **Grey rows** won't be indexed: verse-only ("v. 23"), chapter-only
     ("Proverbs 5"), possible titles in italics, and volume:page citations
     ("HALOT, 1:93").
   * Double-click a row (or press Space) to include or exclude it. Use
     **Edit reference…** to correct a book or verse.
   * The **Show** menu filters to the rows that need checking.
   * **Add reference…** tags anything the scan missed: search for the words where
     it occurs, pick the spot, and type the reference.
3. Choose **Page Number Separation**: comma and space; right-aligned (tab) with or
   without a dot leader; em space; en space; word space; em dash (spaced or closed);
   spaced en dash; or **Custom…**, where you type up to five characters (Word's
   limit), e.g. ` —— `.
4. Click **Build index…**. If any references are in footnotes or endnotes, you
   choose how their page numbers appear:

   **Index stays live** (the index is a Word field; select it and press F9 after edits)
   * Don't index references in notes
   * Italic page numbers
   * Bold page numbers

   **Final step: index becomes plain text** (needs Word)
   * Highlight the note page numbers so "n#" can be added by hand
   * Add the note number automatically (`33n12`; `33nn11–12` for several notes)

   With the final-step options you get **two copies**: `… - Scripture Index.docx`
   keeps a live index, and `… - Scripture Index (final).docx` has the plain-text
   index with the note page numbers completed or highlighted. If the layout
   changes later, update the live copy (or rebuild) and run the final step again.
   In the automatic mode, a page number is highlighted only when the tool can't
   tell for certain which note it belongs to. Those are listed in the Messages box
   and in the proof list.

### Making a static copy of a checked index

When the live index has been checked (for example, an author has confirmed the
bold page numbers really are the note references), choose **Make static copy…**
(also under **Tools**). Pick the indexed document and choose:

* **Add the note number** (`33n12`) or **highlight** the note page numbers;
* how note page numbers are marked in the live index: detect automatically from
  the index entry fields, bold, italics, or nothing (then they're matched by page);
* whether to **update the index first**. Leave this off if you corrected the
  index by hand, because updating rebuilds it from the entry fields.

The tool opens the document read-only and saves `… (static index).docx` next to it
(or in the "Save results to" folder). Only the index becomes plain text; the index
entry fields in the text stay, so the document can be re-indexed later. Existing
files are never overwritten: a second run saves `(static index 2)`, and so on.
This needs Word.

### "Open the copy in Word to build the index and read page numbers"

A .docx file doesn't contain page numbers; only Word knows where pages break once
it lays the document out. With this option on (the default when Word is
installed), the app:

1. starts a hidden copy of Word in the background and opens the indexed copy;
2. updates every field, so the index (and the table of contents) is built;
3. reads the printed page number of each reference and each note's number, so the
   proof list can be sorted by page;
4. for the final-step note options, writes `n#` or highlighting into the finished index.

Your own open Word windows aren't touched. With the option off, the app only
writes the copy: the index shows a placeholder until you open it in Word and
press Ctrl+A, F9; the proof list is in reading order without page numbers; and
the final-step note options aren't available. Turn it off only if Word isn't
installed, or if automation is blocked on that computer.

## Languages, abbreviations and books

**Tools > Settings** has three tabs. Everything in it can be exported to a file
(**Tools > Export settings**) and imported into any later version, or shared
with a colleague.

* **Languages & abbreviations.** Each language recognizes full names plus one or
  more abbreviation sets, which you can switch on or off. For each book you can
  change the name printed in the index, add abbreviations your house style uses,
  or stop a spelling from being recognized.

  | Language | Abbreviation sets (source) | Notes |
  |---|---|---|
  | English | SBL; CMOS traditional; CMOS shorter; other common forms | "1", "I", "First" all work |
  | Español | Reina-Valera / standard Spanish forms | "Primera de Corintios" works |
  | Português | Almeida | "Jo" = João, "Jn" = Jonas |
  | Français | Bible de Jérusalem / TOB; Segond | "Jn 3,16", "3,16.18", "4s." |
  | Deutsch | Loccumer Richtlinien; Luther/traditional | "Joh 3,16", "1. Mose", "13,4ff." |
  | עברית | common abbreviations (unconfirmed — please review) | Hebrew-letter numerals (ג, טז / ג:טז), prefixes (בבראשית), Tanakh order |

  In languages that write chapter and verse with a comma (French, German), and in
  Hebrew, a reference with no book name is only taken from context when it's in
  parentheses, so "3,5 Euro" isn't mistaken for a verse. Two-letter abbreviations
  that are also ordinary words (English "Is", "Am"; Spanish "Os"…) need a
  chapter *and* verse after them.

  For the Apocrypha, abbreviations in other languages are included only where a
  published standard confirmed them (French, German, Spanish); add the rest for
  your style. Hebrew names for the New Testament and Apocrypha are starter forms
  to check.
* **Index sections.** The order of sections (default: OT, Apocrypha, NT, Other),
  editable section headings for each language, and the Old Testament order:
  English Bible order, or Tanakh order (JPS/Koren, the Hebrew default, or BHS).
  Planned sets — Dead Sea Scrolls, Josephus, Philo, Rabbinic literature,
  Pseudepigrapha, Apostolic Fathers — are listed but not available yet.
* **Custom books.** Add any work a book or dissertation cites (e.g. *1 Enoch*):
  its name, other spellings, abbreviations, section, position and chapter count.

## InDesign

**Tools > Export InDesign script (.jsx)** writes a script with your current
language, abbreviations and custom books built in. In InDesign, open **Window >
Utilities > Scripts**, right-click **User** > **Reveal in Explorer**, copy the
.jsx there, open your document and double-click the script. It asks:

* how to treat references in **footnotes** (don't index; index with page numbers
  in italics or bold through a character style; or index plainly);
* the **index layout** (one index; OT/NT; by section);
* whether to **highlight references whose book came from context** with a
  non-printing condition ("Scripture Index: check book" — delete the condition
  when you're done);
* whether to remove Scripture topics from an earlier run;
* the **proofreading list** format: **HTML** (default), **CSV** or **both**,
  saved next to the document.

It remembers your choices. It then adds index topics (with canonical sort order)
and page-reference markers; generate the index with **Window > Type & Tables >
Index > Generate Index**. The whole run is one Undo step.

The script's parser is a translation of the app's parser into InDesign's older
JavaScript. A test compares the two on every test sentence and on real
manuscripts; they must give identical results.

## Checking for updates

**Help > Check for updates** (and a quiet check at start-up) will compare your
version with the latest release once the project is published on GitHub; set
`UPDATE_REPO` in `scripture_index/updates.py` to the repository name. The
workflow in `.github/workflows/build.yml` builds the .exe and the InDesign
script, runs all tests, and publishes a release whenever a tag like `v0.2.0` is
pushed.

## What it recognises

* Full names and abbreviations, with or without periods, and non-breaking spaces.
* Lists that carry the book forward (`Prov. 1:1; 10:1; 25:1`, `2:7, 3:5, and 8:4`)
  and verse continuations (`5:1, 7` → 5:1 and 5:7; German `8,28.30`).
* Bare references whose book comes from earlier text. Notes inherit the book in
  force at the point where their reference mark sits.
* Cross-chapter ranges are kept whole (`5:9–6:1`), and sort canonically
  (`7:11–13` before `7:11–8:7`).
* Text inside existing tables of contents and indexes is ignored.

Names that are also people or common words (John, James, Peter, Acts, Numbers,
Job; Juan, Santiago…) only set the book when a number follows or when they're
introduced by "the book of" / "Gospel of" (or the language's equivalent).

## Known limits in 0.2.0

* The Word index is added at the end of the document in its own section. Move
  it afterwards if it belongs before an appendix or "About the Author".
* An existing INDEX field isn't removed automatically. Delete the old index
  first; the app warns you. Old XE fields can be removed with the checkbox.
* If a reference appears in the body and in a note on the same page, Word prints
  one page number. The proof list flags these cases.
* Accept or reject tracked changes before building.
* InDesign: index markers inside footnotes depend on your InDesign version; any
  marker that can't be placed is listed in the proofreading list. Footnote
  numbers in the InDesign proof list count footnotes in story order.

## Running from source / tests

```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python run_app.py                       # GUI
python -m scripture_index scan  "Book.docx"
python -m scripture_index build "Book.docx" --notes auto --sep tab_none
python -m scripture_index static "Book - Scripture Index.docx" --mode auto
python -m scripture_index jsx "Scripture Index Builder.jsx" --lang es
python tests\test_parser.py           # parser tests, all languages
python tests\js_parity.py Book.docx   # Python vs InDesign parser (needs Node.js)
python tests\indesign_mock_test.py    # InDesign script against a fake document
```

## Planned

* More languages (Dutch, Afrikaans, Swahili, Turkish, …).
* Dead Sea Scrolls, Josephus, Philo, Rabbinic literature, Pseudepigrapha and
  Apostolic Fathers sets, with their own citation formats.
