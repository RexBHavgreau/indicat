# Indicat: notes for Claude

Indicat builds Scripture, Greek/Hebrew word, and term (subject) indexes for Word manuscripts,
InDesign documents (through a generated script), and finished PDFs. It is a Windows tkinter app,
GPL-3.0, "Indicat, created by Beaux Hargrove". Repo: github.com/RexBHavgreau/indicat.

## Working with Beaux

- Keep reports short and plain (the KISS rule): what changed, what was tested, what wasn't.
  No long recaps.
- Beaux uses Windows. Build for Windows; test on Windows when you can (real Word, real InDesign).
- **Ask before merging to `main` or tagging a release.** Work on a branch (e.g. `v0.5.0-dev`)
  and push it; Beaux merges.
- He is an editor and Hebrew/OT scholar: the index conventions follow the Chicago Manual of
  Style and SBL. When in doubt about an editorial choice, ask rather than guess.

## Releases

- Version is in `indicat/__init__.py`; add a dated entry at the top of `CHANGELOG.md`.
- Pushing a tag `vX.Y.Z` runs `.github/workflows/build.yml` on Windows: all tests, the .exe
  (PyInstaller, named "Indicat X.Y.Z.exe"; the tag must match `__version__`), a check that
  Indicat writes the InDesign script (not published), a check that the .exe carries its data
  files, and a GitHub Release with the .exe only. GitHub writes spaces in release file names as
  dots ("Indicat.0.4.1.exe"); the updater saves it as "Indicat 0.4.1.exe". The workflow can also be started by hand (workflow_dispatch) on any branch
  to check a build without releasing.
- Settings carry over between versions (`%APPDATA%\Indicat\settings.json`). When the layout of
  settings changes, bump `SETTINGS_VERSION` and add a step to `migrate()` in
  `indicat/settings.py`, so saved settings are upgraded rather than lost.

## Layout

| Path | What it is |
|---|---|
| `indicat/parser.py` | Scripture reference parser (statuses, context, ranges, f/ff, MT, old styles) |
| `indicat/profiles.py`, `lang.py`, `catalog.py` | Languages, book names, abbreviation sets, sections, verse counts |
| `indicat/terms.py` | Word indexes (Greek/Hebrew/Syriac/tagged), dictionary forms, term sets |
| `indicat/docx_io.py` | Reading/writing .docx: segments, notes, headings, bibliography, XE fields, index styles |
| `indicat/pipeline.py` | Scan and build for Word (inclusion rules, outputs) |
| `indicat/word_com.py` | Word automation (COM): fields, page numbers, n#, static copies, CMOS cross-refs |
| `indicat/pdf_io.py`, `pdf_index.py`, `static_index.py`, `pdf_viewer.py` | The PDF route: reading the text layer, scanning, writing .docx/.odt indexes, opening a page |
| `indicat/proof.py` | Proofreading list (.docx and .csv) |
| `indicat/gui.py`, `dialogs.py`, `guided.py` | Main window, Preferences and other dialogs, guided build (Philosopher Mode) |
| `indicat/jsx.py`, `indicat/js/*.js` | The InDesign script: Python builds a DATA block, then parser.js, terms.js, driver.js |
| `indicat/data/` | `lexicon.json` (dictionary forms), `verses.json` (verse counts); built by `tools/build_data.py`, committed |
| `indicat/cli.py` | Command line (`python -m indicat scan/build/static/jsx`) |
| `indicat/updates.py` | Update check, install beside the running copy, old copies and shortcuts |
| `tests/` | See below |

## The one rule that matters most

**The InDesign JavaScript must give exactly the same results as the Python.** Every change to
the Scripture parser (`parser.py`, `lang.py`, profile data) must be ported to
`indicat/js/parser.js`, and every change to word/term matching (`terms.py`) to
`indicat/js/terms.js`. New data the JS needs goes into `jsx.build_data()` / `terms_data()`.
Then run `tests/js_parity.py` and `tests/terms_parity.py` (they need Node.js) and add test
sentences for the new behavior to them.

The JS runs in InDesign's ExtendScript (ES3): no `forEach`/`map`/`indexOf` on arrays, no
`Object.keys`, no `trim`, no regex lookbehind, no `let`/`const`/arrow functions. The parity tests
delete the ES5 helpers to catch this. ExtendScript's `splice` returns `undefined` when it removes
nothing; `tests/indesign_mock.js` imitates that quirk. The generated .jsx is saved as UTF-8 with
a byte-order mark.

## Tests

```
python tests/test_parser.py          # Scripture parser, all languages
python tests/test_terms.py           # word indexes, dictionary forms, term sets, settings migration
python tests/test_note_matching.py   # note page numbers (n#) and Chicago-style See / See also
python tests/test_pdf.py             # the PDF route (needs reportlab)
python tests/test_styles.py          # template for PDF indexes; the copy's index styles
python tests/test_updates.py         # the updater (download, checks, fall-backs, old copies, shortcuts)
python tests/js_parity.py [Book.docx ...]     # Python vs InDesign parser (needs Node.js)
python tests/terms_parity.py [Book.docx ...]  # Python vs InDesign word/term engine
python tests/word_mock_test.py       # Word automation against a fake Word
python tests/indesign_mock_test.py   # the InDesign script against a fake document
```

Run them all before pushing; CI runs the same list. On Windows set `PYTHONUTF8=1` (Greek and
Hebrew in the console).

**The test kit** (`Indicat Test Manuscript.docx`, `Answer key.csv`, term sets; kept outside the
repo, Beaux has it) tags every test passage ([A01], [B08], [G07], [T03]…). A = Word layout and
notes, B = Scripture, G = Greek/Hebrew, T = term sets. The answer key gives the expected result
for each tag. It is set in Times New Roman throughout. Use it for real Word and InDesign runs,
and for the PDF route (save it as PDF and scan that).

## Conventions in the code

- Statuses of a Scripture hit and which are indexed by default: see the docstring at the top of
  `parser.py`. Inclusion rules that depend on settings (whole chapters, [MT]) are in
  `pipeline.include_by_default`.
- An unknown word before a reference is never filled in from context; it gets a suggestion.
- Word: the index field is placed after the reference, so a reference split across pages takes
  the page where it ends; the PDF route does the same.
- Locators for notes: "143n12", several notes on a page "143nn4–5"; a body reference on the same
  page covers its notes (CMOS).
- Cross-references follow CMOS: "favor. *See* grace"; "Assumption, 9. *See also* Dormition";
  several targets alphabetical, separated by semicolons.
- The user's original document is never modified; outputs are copies.
- User-facing text is plain and specific (say what to do, not what went wrong internally).

## Not yet checked in the real programs (as of 0.4.1)

- 0.4.1: the update in place on Windows (0.4.1 updating to a later release): download, start
  the new version, delete the old one, shortcuts and taskbar pins retargeted (Windows may only
  show a changed pin after signing out); SmartScreen/antivirus on the downloaded .exe.
- 0.4.1: the leader fix in real Word (`word_com._update_indexes` sets `Index.TabLeader` from the
  'index 1' style before updating, and puts the styles' leader back after); a PDF index from a
  real Normal.dotm and from a book template.
- 0.4.1: two-column PDFs checked on 9 pages of the BiblicalMissions textbook (pp. 7–14, 880;
  impossible references 28 → 1, the one left is the book's own "2 Pet 3:14–19"); not yet on
  the whole book, nor on a PDF exported as two-page spreads.

- Word: italic "See" in the live index; Chicago-style cross-references in the finished copy; the
  note-page fixes for term sets (notes running onto the next page, endnotes, a term twice in one
  note).
- InDesign: the new options, bibliography detection, and the script's cross-reference settings
  (`indexGenerationOptions.beforeCrossReferenceSeparator`, `crossReferenceStyle`), which are
  guarded with try/catch and fall back to a message.
- PDF reader page jumps in Acrobat, SumatraPDF, Foxit and the browsers.
- With Greek and Hebrew both on, the InDesign script is about 2 MB (the dictionary forms); check
  how long InDesign takes to start it.

## Ideas parked for later

See also `PLANS.md` (the working list, a Mac version for a contributor, and what was decided
against, e.g. live .odt indexing).

- More languages; Dead Sea Scrolls, Josephus, Philo, Rabbinic, Pseudepigrapha, Apostolic Fathers
  citation sets; page ranges for term-set entries.
