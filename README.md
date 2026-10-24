# ☞ Indicat

**Indicat** (Latin, "it points out") is a tool for editors and authors that
builds indexes for Word manuscripts, for InDesign documents through a
generated script, and for finished books as PDFs:

* a **Scripture index** in canonical order, including references whose book is
  only known from context;
* **Greek, Hebrew/Aramaic and Syriac word indexes**, which leave quotations out and
  file Greek and Hebrew words under their dictionary form (λόγου → λόγος);
* **word indexes for other languages** (Latin, German…) the manuscript tags;
* **term indexes** built from your own lists, such as a subject index.

It also writes a **proofreading list** of every indexed entry, sorted by page.

Created by **Beaux Hargrove**. Free software under the GNU GPL v3
([license and credit](#license-and-credit)).

Your original manuscript is never changed. The app writes:

| File | What it is |
|---|---|
| `<name> - Indexed.docx` | A copy of the manuscript with an index entry (XE) field after every entry and the indexes at the end |
| `<name> - Indexed (final).docx` | Only with the "final step" note options: the same, with plain-text indexes and note page numbers completed (33n12) or highlighted |
| `<name> - Index Proof List.docx` | Every indexed entry by page, with context, how it was found, and a checkbox; then everything found but *not* indexed |
| `<name> - Index Proof List.csv` | The same data for Excel |
| `<name> - Index.docx` or `.odt` | From a PDF: the finished index, with the printed page numbers |

## Build the .exe (once per version)

1. Install Python 3.10 or newer from python.org and tick **Add python.exe to PATH**.
2. Double-click **`build_exe.bat`**. It creates a private environment in `.venv`,
   installs the requirements and PyInstaller, and builds the app.
3. The program is `dist\Indicat 0.4.1.exe` (each version carries its number in
   its name). It runs on its own and can be copied to any Windows PC. Other
   users don't need Python.

Every release on GitHub also has a ready-made program to download (GitHub
writes the name with dots, "Indicat.0.4.1.exe"). The InDesign script isn't in
the release: make it from the app (**Tools > Export InDesign script**), so it
carries your settings.

## Using it

The first time Indicat starts it offers a **guided index build** (Philosopher
Mode), which goes through the settings one step at a time and explains each
choice: the document, what to index, language and abbreviations, how the index
looks (with a live preview), notes, then the scan, with a word on what to check,
and a summary before building. It's also under **Help > Guided build** and the
**Guided build…** button. Everything it sets shows in the main window, and the
next build starts from the same settings.

In the main window:

1. **Browse** to the manuscript (.docx) or a PDF. Results are saved in the same
   folder unless **Edit > Preferences** says otherwise (a fixed folder, or ask
   each time); changing the folder in the window applies to that build only.
2. Set the **index settings for this book** (also in the **Index** menu): title,
   columns, language, layout (one index; Old/New Testament; or by section), page
   number separation, and
   * **Index the Apocrypha**: Apocrypha references are always recognized, so
     they're never mistaken for another book; with this off they're listed in
     grey and left out;
   * **Index references to whole chapters** ("Proverbs 5"; off by default);
   * **Index the bibliography** (off by default: a commentary title such as
     *Luke 1:1–9:50* is not a reference to Luke);
   * **Verses cited in Hebrew numbering** ("Joel 2:28 [3:1 MT]"): index the
     Hebrew number too, marked [MT], or leave it out;
   * **Index font**: match the body text (the font of the paragraph style that
     holds the most text) or keep the document's own index styles.
3. Under **Indexes to build**, tick Scripture, Hebrew words, Greek words, and any
   term sets. **Word & term indexes…** sets them up.
4. Click **Scan**. A progress bar shows how far it has got.
5. Review the list.
   * **Yellow rows** are indexed but worth a look: the book came from context, a
     name needs checking ("3 Kings" = 1 Kings, Vulgate numbering), a verse is in
     Hebrew numbering, or a PDF's OCR was read through ("Gen. l:l").
   * **Blue rows** are open-ended references ("Rev 2:18ff."): indexed, and sorted
     after 2:18 and before 2:18–19.
   * **Grey rows** won't be indexed: verse-only ("v. 23"), whole chapters,
     possible titles in italics, volume:page citations ("HALOT, 1:93"),
     impossible verses ("Joel 1:118"), quotations, the bibliography, the
     Apocrypha when it isn't indexed, and **unknown book names**. An unknown name
     is never filled in from context; the row suggests what it might be
     ("Ex. → Exodus? (from CMOS shorter, switched off)", "Geneses → Genesis?").
   * Click a **column heading** to sort by it (Entry sorts in Bible order, then
     alphabetically); click again to reverse; **Reading order** goes back.
     **Show**, **How found**, **Where** (body, footnotes, endnotes) and the index
     filter combine.
   * Double-click a row (or press Space) to include or exclude it. **Edit…**
     corrects a reference or files a word under another heading. **Add
     reference…** tags one the scan missed. For a PDF, **Open PDF at this page**
     opens the page in your PDF reader.
6. Click **Build index…**. If any entries are in footnotes or endnotes, you
   choose how their page numbers appear:

   **Index stays live** (the index is a Word field; select it and press F9 after edits)
   * Don't index entries in notes
   * Italic page numbers
   * Bold page numbers

   **Final step: index becomes plain text** (needs Word)
   * Highlight the note page numbers so "n#" can be added by hand
   * Add the note number automatically (`33n12`; `33nn11–12` for several notes)

   With the final-step options you get **two copies**: `… - Indexed.docx`
   keeps live indexes, and `… - Indexed (final).docx` has plain-text indexes
   with the note page numbers completed or highlighted, and cross-references in
   Chicago style ("favor. *See* grace"; "Assumption, 9. *See also*
   Dormition"). If the layout changes later, update the live copy (or rebuild)
   and run the final step again. In the automatic mode, a page number is
   highlighted only when the app can't tell for certain which note it belongs
   to. Those are listed in the Messages box and in the proof list. When the
   status bar says "Index built in …", it's done.

Each index starts with its own heading: "Scripture Index" (or the Old Testament,
New Testament… sections), then "Index of Hebrew and Aramaic Words", "Index of
Greek Words", and your term indexes. Every title can be changed in the settings.

**Index settings and Preferences.** The settings in the main window and the
**Index** menu belong to the book you're indexing; Indicat starts with the ones
you used last. **Edit > Preferences** holds the rest: where results are saved,
whether to use Word, your PDF reader, the template for indexes made from a PDF,
update checks, abbreviation sets and
book names, custom books, section order and titles, the word-index options and
skip lists, your term sets, and export/import.

## Indexing a PDF

Choose a PDF instead of a .docx. Indicat reads the PDF's text layer, so the PDF
must have one: born digital (exported from Word, InDesign…), or scanned and
**OCR'd** (Indicat doesn't do OCR itself). It builds a finished index straight
from the printed page numbers, as a **Word (.docx)** or **OpenDocument (.odt)**
file, plus the usual proofreading list. LibreOffice users can export their book
to PDF and index it this way.

**Only some pages.** A box under the manuscript, **PDF pages to index**, takes
PDF page numbers (1 = the PDF's first page, as your PDF reader shows them):
"9–880", or several ranges, "9–14, 21–880". Leave it blank for the whole book.
Use it to leave out the title page, contents, endorsements and other front or
back matter. It shows which printed pages the range covers, and Indicat keeps
the range for that PDF. The book's own index is left out anyway.

The Word index starts from **Word's Normal template**, so it has your usual page
size, margins and styles; choose another template, or Indicat's plain style, in
**Edit > Preferences**. Indicat's own settings still apply on top: columns,
right-aligned page numbers and their leader, and the index font.

What it works out from the pages:

* **Page numbers**: the folios printed in the running heads or feet (roman front
  matter included), checked against each other; failing that, the PDF's page
  labels.
* **Running heads and folios** are left out (found by their place on the page and
  their repetition from page to page).
* **Footnotes**: the block of smaller type at the foot of the page, under a rule
  or starting with a note number. References in notes get "143n12" (or italics,
  bold, or nothing, as you choose); a note that runs onto the next page keeps its
  number there. Pages of notes alone are read as endnotes ("16ni").
* **Note marks** in the text (superscript numbers) are taken out, so "renewed²
  (Josh. 24:25)" isn't misread, and they tell each note where its book comes from.
* **Hyphenation**: a word broken at the end of a line is joined when the whole
  word is a book name or a term ("Ec-cles. 7:26"). A word broken across a page
  ("Deu-‖143‖teronomy 6:4") is flagged as a *possible interrupted term*, with
  the joined word suggested, and not indexed until you include it.
* **Older citation styles** are read in PDFs: roman chapter numbers ("Matt. v.
  3", "Ps. cxix. 105", and lists such as "Heb. iii. 7, ix. 8, x. 15"), chapter and verse words ("ch. iii. ver. 4"), and period
  abbreviations (Cant., Eccles., Ecclus., Wisd., 1 Paralip. — flagged as the
  Vulgate name).
* **OCR'd PDFs**: common slips are read through and flagged ("l" or "I" for 1,
  ";" for ":"), and only the Scripture index and term sets are built (OCR'd
  Greek and Hebrew aren't reliable enough to index word by word). Pages whose
  text is missing, thin or garbled compared with the rest of the book are listed
  so you can check them by eye.
* The book's own printed index, if it has one, is left out of the scan; the
  bibliography is handled as in Word documents.

**Open PDF at this page** works with Acrobat and Acrobat Reader, SumatraPDF,
Foxit, Edge, Chrome and Firefox (choose one in Preferences, or let Indicat find
one). Any other program opens the PDF and Indicat tells you which page.

## Original-language word indexes

**Index > Original-language word indexes** (or **Word & term indexes…**).

Greek, Hebrew/Aramaic and Syriac each have their own alphabet, so the app finds
every word written in them by its letters alone. Each is its own index, and each
can be switched on and off.

**What counts as a word to index.** An index is meant to point to the places
where a word is *discussed*, not to every word of a quotation. So the app leaves
quotations out:

* **Block quotations** are skipped whole: paragraphs in a quotation style
  (any style named Quote, Block Text, Block Quotation, Extract…), and indented
  paragraphs of prose (indented 0.4 in or more, not numbered, at least a dozen
  words long). A short indented line, such as one word of a vocabulary list, is
  not treated as a quotation.
* **Inline quotations**: within a paragraph, more than **four** Greek or Hebrew
  words in a row (the number can be changed) are a quotation and are skipped…
* …**unless they are a list**: words separated by commas, semicolons or slashes,
  where each item is no longer than **two** words (also adjustable). "The verbs
  ἀγαπάω, φιλέω, στέργω, ἐράω, and ποθέω" is indexed word by word; "ἐν ἀρχῇ ἦν ὁ
  λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν" is a quotation.
* **Tables** are read cell by cell, so a paradigm or word list in a table is
  indexed.

Skipped quotations are listed as grey rows in the review table and under "Not
indexed" in the proofreading list. If the author does discuss the words of one,
include it and every word in it is indexed.

**Dictionary forms.** Greek and Hebrew words are filed under their dictionary
form (lemma): λόγου, λόγῳ and λόγοις under λόγος; κεχαριτωμένη under χαριτόω;
וְהָאָרֶץ and הָאָרֶץ under אֶרֶץ; וַיִּתְהַלֵּךְ under הָלַךְ. The forms come from the
Greek New Testament (MorphGNT) and the Hebrew Bible (Open Scriptures Hebrew
Bible), and a dictionary form cited by itself files under itself. A form that
isn't in them stays as written. An unpointed Hebrew form that could be more than
one word (דבר: דָּבָר, דָּבַר or דֶּבֶר) is filed under the most common one and marked
yellow, saying what else it could be. Optionally, the forms printed in the book
are listed as subentries under each dictionary form. Both options are in the
word-index settings.

**Grouping forms.** Forms that differ only in accents, breathings, vowel points
or cantillation marks are one entry: λόγος, λογος and Λόγος; דָּבָר and דבר. The
entry is printed in its fullest form (pointed or accented). Switch this off to
keep every exact form separate.

**Words to skip.** Each index has an editable list of words that are never
indexed: articles, conjunctions and common prepositions (ὁ, καί, δέ, ἐν…;
את, אשר, כי…), and for Greek also the personal pronouns (ἐγώ, σύ, ἡμεῖς, ὑμεῖς
and their forms), τίς/τί, and the forms of εἰμί. Elided forms count as the full
word: δι’ is διά, κατ’ and καθ’ are κατά, and so on. With dictionary forms on, a
word whose dictionary form is in the list is skipped too. Accents and vowel
points don't matter in the list. Words shorter
than two letters are also skipped (adjustable).

Words are sorted in the order of their alphabet (α–ω; א–ת, with final forms
sorted as their regular letters).

**When the book itself is in Hebrew.** A Hebrew word index would list every word
of a Hebrew book, so it stays off when the language is set to Hebrew. To index
the (ancient) Hebrew words such a book discusses, build a term set listing them.
The same goes for a Greek book, or a book in Neo-Latin.

**Other languages (Latin, German, …).** Languages written in the same alphabet
as the book can't be told apart by their letters, so these indexes take only the
words the manuscript **tags** with that language. In Word, select the text and
choose Review > Language > Set Proofing Language. Add a language on the **Other
languages** tab. For words that aren't tagged, use a term set.

> **Older Greek and Hebrew fonts.** Some older manuscripts type Greek or Hebrew
> with "legacy" fonts such as SPIonic, SPTiberian, BWGRKL, BWHEBB, Graeca or
> TekniaGreek. In those fonts the text is really Latin letters
> (for example "lo/goj") that only *look* Greek or Hebrew on screen, so the app
> can't recognize it as Greek or Hebrew. Convert such text to Unicode first
> (the converters published with those fonts can do it), or index those words
> with a term set that lists them as they are typed.

## Term sets

**Tools > Term sets** (or **Word & term indexes…** > Term sets). A term set is a
list of words or names to index, each set in its own index: a subject index, a
list of names, or the Hebrew words a Hebrew-language book discusses.

**Build a new set…** reads a file:

* **Plain text (.txt):** one term per line. The first form on a line is the
  heading; other forms to find go after a vertical bar. Lines starting with #
  are ignored.

  ```
  covenant | covenants
  λόγος | λόγου | λόγῳ | λόγον
  חֶסֶד | חַסְדּוֹ
  ```

* **CSV (.csv), e.g. saved from Excel**, with these columns (a header row is
  optional; **Save a sample CSV…** writes one to start from):

  | heading | subentry | match forms | sort as | see | see also |
  |---|---|---|---|---|---|
  | covenant | | covenant \| covenants | | | |
  | covenant | new | new covenant | | | |
  | hesed | | | | חֶסֶד | |
  | justification | | justification \| justified | | | sanctification |

  * **match forms**: the forms to find, separated by `|`. If blank, the
    subentry (or the heading) is used.
  * **sort as**: sorts the heading as if it were written this way.
  * **see**: makes the line a cross-reference only ("hesed. *See* חֶסֶד");
    nothing is matched for it.
  * **see also**: adds "*See also* …" to an entry that is also matched.

Each set has its own **index title** and **matching options**: match capitals
exactly; ignore accents, breathings and vowel points (on by default); whole
words only (on by default); also match simple English plurals (-s, -es); also
match Hebrew words with prefixes (ו ה ב כ ל מ ש); skip block quotations (on by
default). Sets are switched on and off like the other indexes, saved with your
settings, exported with them, and can be exported back to CSV to edit in Excel.

> **A term set works like a concordance.** It finds every place a listed form
> appears, but it can't tell whether a passage is really *about* the term. Review
> the rows before building and exclude passing mentions. An index built from a
> list still needs an indexer's judgment.

## Making a static copy of a checked index

When the live index has been checked (for example, an author has confirmed the
bold page numbers really are the note references), choose **Tools > Make a
static-index copy**. Pick the indexed document and choose:

* **Add the note number** (`33n12`) or **highlight** the note page numbers;
* how note page numbers are marked in the live index: detect automatically from
  the index entry fields, bold, italics, or nothing (then they're matched by page);
* whether to **update the index first**. Leave this off if you corrected the
  index by hand, because updating rebuilds it from the entry fields.

The app opens the document read-only and saves `… (static index).docx` next to
it (or where Preferences says results go). See and See also are set in Chicago
style. Only the indexes become plain text; the
index entry fields in the text stay, so the document can be re-indexed later.
Existing files are never overwritten: a second run saves `(static index 2)`, and
so on. This needs Word.

## "Open the copy in Word to build the index and read page numbers"

A .docx file doesn't contain page numbers; only Word knows where pages break once
it lays the document out. With this option on (the default when Word is
installed), the app:

1. starts a hidden copy of Word in the background and opens the indexed copy;
2. updates every field, so the indexes (and the table of contents) are built;
3. reads the printed page number of each entry and each note's number, so the
   proof list can be sorted by page;
4. for the final-step note options, writes `n#` or highlighting into the finished indexes.

Your own open Word windows aren't touched. With the option off, the app only
writes the copy: the indexes show a placeholder until you open it in Word and
press Ctrl+A, F9; the proof list is in reading order without page numbers; and
the final-step note options aren't available. Turn it off only if Word isn't
installed, or if automation is blocked on that computer.

## Languages, abbreviations and books

**Edit > Preferences** holds:

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
* **Original-language words**, **Other languages** and **Term sets** (above).

## Your settings

Settings are kept in `%APPDATA%\Indicat\settings.json`. **A new version uses
them automatically**: every version of Indicat reads the same file, and the
first time Indicat runs it also brings over the settings of Scripture Index
Builder 0.2 (and says so in the Messages box). The InDesign script likewise picks
up the choices you made in the earlier script.

**Edit > Export settings** still saves everything (languages, abbreviations,
custom books, sections, word-index options and term sets) to a file, to move to
another computer or share with a colleague; **Import settings** reads it.

## InDesign

**Tools > Export InDesign script (.jsx)** writes "Indicat for InDesign.jsx" with
your current language, abbreviations, custom books, word indexes and term sets
built in (export it again after changing them). In InDesign, open **Window >
Utilities > Scripts**, right-click **User** > **Reveal in Explorer**, copy the
.jsx there, open your document and double-click the script. It asks:

* which indexes to build (Scripture, and each word index or term set);
* how to treat entries in **footnotes** (don't index; index with page numbers
  in italics or bold through a character style; or index plainly);
* the Scripture **index layout** (one index; OT/NT; by section);
* whether to **highlight references whose book came from context** with a
  non-printing condition ("Scripture Index: check book" — delete the condition
  when you're done);
* whether to remove topics from an earlier run;
* the **proofreading list** format: **HTML** (default), **CSV** or **both**,
  saved next to the document.

It remembers your choices. It adds index topics (with sort order) and
page-reference markers, plus See / See also cross-references from term sets;
generate the index with **Window > Type & Tables > Index > Generate Index**. The
whole run is one Undo step.

An InDesign document has a single index, so each word index and term set
becomes a **top-level entry** of it ("Index of Greek Words", "Subject Index"),
with its words underneath. After generating, move each into its own section and
style it. InDesign has no Latin language setting, so use a term set for Latin
there.

The script's parser and word/term engine are translations of the app's into
InDesign's older JavaScript. Tests compare them on test sentences and on real
manuscripts; they must give identical results.

## Checking for updates

**Help > Check for updates** (and a quiet check at start-up) compares your
version with the latest release at
[github.com/RexBHavgreau/indicat](https://github.com/RexBHavgreau/indicat). When
there is a newer one, Indicat offers to **install it in the same folder** as the
version you're running: it downloads the new program (named with its version,
so the running one is never overwritten), checks that it arrived intact, and
offers to start it. If the folder can't be written to (for example, under
Program Files), the new version is saved in your Downloads folder instead.
At its first start the new version offers to **delete the old one** and to
point your desktop, Start menu and taskbar shortcuts to itself. Settings carry
over either way.

The repository must be public and have at least one published release. The
workflow in `.github/workflows/build.yml` runs all tests, builds the program,
checks that it writes the InDesign script, and publishes a release whenever a
tag like `v0.4.1` is pushed. The tag must match the version in
`indicat/__init__.py`, and releases must keep that pattern (v0.4.2, v0.5.0…).

## What it recognizes (Scripture)

* Full names and abbreviations, with or without periods, and non-breaking spaces.
* Lists that carry the book forward (`Prov. 1:1; 10:1; 25:1`, `2:7, 3:5, and 8:4`)
  and verse continuations (`5:1, 7` → 5:1 and 5:7; German `8,28.30`).
* Bare references whose book comes from earlier text. Notes inherit the book in
  force at the point where their reference mark sits.
* Cross-chapter ranges are kept whole (`5:9–6:1`), and sort canonically
  (`7:11–13` before `7:11–8:7`).
* Text inside existing tables of contents and indexes is ignored.
* "f" and "ff": `34f` is 34–35 (flagged when no verse follows); `34ff.` is kept
  as written and sorts after 34 and 34a, before 34–35 (German "f./ff." and
  French "s./ss." alike). Short ranges are read in full: `16–7` is 16–17.
* Chapters and verses are checked against the Bible's verse counts (English and
  Hebrew numbering), so "Joel 1:118" is flagged as impossible.
* Hebrew numbering: "Mal 3:23 [4:5]" or "51:3 in the MT" marks the Hebrew number
  [MT] (or leaves it out, as you choose).
* Gospel writers as subjects ("Matthew uses it (16:21)") set the book; a person
  who shares a book's name ("Zechariah responds (1:20)") doesn't.
* After "1 Kings 1–11", a bare "verse 23" is flagged: the chapter is unclear.
* An italic reference right after an author's name ("Bock, *Luke 1:1–9:50*") is
  a title; a number right after an italic title ("*Mariology*, 1:118") is a
  volume:page citation; references in an italic "cf." list are indexed.

Names that are also people or common words (John, James, Peter, Acts, Numbers,
Job; Juan, Santiago…) only set the book when a number follows or when they're
introduced by "the book of" / "Gospel of" (or the language's equivalent).

## Known limits in 0.4.2

* The indexes are added at the end of the document in their own section. Move
  them afterwards if they belong before an appendix or "About the Author".
* An existing INDEX field isn't removed automatically. Delete the old index
  first; the app warns you. Old XE fields can be removed with the checkbox.
* If an entry appears in the body and in a note on the same page, Word prints
  one page number. The proof list flags these cases.
* Accept or reject tracked changes before building.
* PDFs: the text layer has to match the printed page. Pages in two columns are
  read column by column; three or more columns (such as the book's own index,
  which is left out anyway) and text in sidebars are read in layout order, which
  may not be reading order. Adding a reference by hand works with Word manuscripts
  only.
* Live .odt documents can't be indexed directly; export them to PDF and use the
  PDF route.
* Word indexes list single words. A phrase (such as עַם הָאָרֶץ) is indexed as a
  phrase only through a term set.
* InDesign: index markers inside footnotes depend on your InDesign version; any
  marker that can't be placed is listed in the proofreading list. Footnote
  numbers in the InDesign proof list count footnotes in story order.

## Running from source / tests

```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python run_app.py                                 # the app
python -m indicat scan  "Book.docx" --words greek,hebrew
python -m indicat build "Book.docx" --notes auto --sep tab_none --terms "Subjects.csv"
python -m indicat static "Book - Indexed.docx" --mode auto
python -m indicat build "Book.pdf" --notes auto --format odt
python -m indicat jsx "Indicat for InDesign.jsx" --lang es
python tests\test_parser.py           # Scripture parser, all languages
python tests\test_terms.py            # word indexes, term sets, settings carry-over
python tests\js_parity.py Book.docx   # Python vs InDesign Scripture parser (needs Node.js)
python tests\terms_parity.py Book.docx  # Python vs InDesign word/term engine (needs Node.js)
python tests\test_note_matching.py    # note page numbers and Chicago-style cross-references
python tests\test_pdf.py              # the PDF route (needs reportlab)
python tests\word_mock_test.py        # Word automation against a fake Word
python tests\indesign_mock_test.py    # InDesign script against a fake document
```

## Support Indicat

Indicat is free. If it saves you time on a book or dissertation, you're welcome
to support its development with a donation. (Donation link coming soon. To
switch on GitHub's **Sponsor** button, add `.github/FUNDING.yml` naming the
donation page.)

## License and credit

Indicat, created by **Beaux Hargrove**. Copyright © 2026 Beaux Hargrove.

Free software under the [GNU General Public License, version 3](LICENSE), with
additional terms in [NOTICE.md](NOTICE.md): every copy and modified version must
keep the credit "Indicat, created by Beaux Hargrove" in its About box, its
documentation and the InDesign scripts it generates, and a modified version
that is distributed must use a different name and icon.

Greek and Hebrew dictionary forms: MorphGNT (CC BY-SA 3.0) with the SBL Greek
New Testament, and the Open Scriptures Hebrew Bible and Hebrew Lexicon (CC BY
4.0). Verse counts: the King James Version (public domain), the Westminster
Leningrad Codex (public domain) and the SBLGNT. Details in NOTICE.md.

## Planned

* More languages (Dutch, Afrikaans, Swahili, Turkish, …).
* Dead Sea Scrolls, Josephus, Philo, Rabbinic literature, Pseudepigrapha and
  Apostolic Fathers sets, with their own citation formats.
* Page ranges for term-set entries.
