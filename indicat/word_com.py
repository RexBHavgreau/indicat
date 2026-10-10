"""Drive Microsoft Word (Windows, via COM) to paginate the indexed copy.

Word is the only thing that knows where pages break, so this module:
  1. opens the indexed copy invisibly and updates every field (TOC, INDEX);
  2. reads the printed page number (respecting roman/arabic sections) of every
     hidden bookmark the builder placed next to each reference;
  3. works out each note's displayed number;
  4. for the "highlight" and "auto" note modes, edits the generated index:
     italic (note) page numbers become highlighted, or get "n12" appended,
     and the index is then converted to plain text so Word won't regenerate it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from .profiles import PROFILES
from .catalog import ENGLISH_FALLBACK

WD_ADJ_PAGE = 1          # wdActiveEndAdjustedPageNumber
WD_SECTION = 2           # wdActiveEndSectionNumber
WD_PAGE = 3              # wdActiveEndPageNumber
WD_FIELD_INDEX = 8       # wdFieldIndex
WD_YELLOW = 7            # wdYellow
WD_ALERTS_NONE = 0
WD_PRINT_VIEW = 3        # wdPrintView
WD_FIELD_INDEX_ENTRY = 4  # wdFieldIndexEntry (XE)


def available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401
        import pythoncom  # noqa: F401
        return True
    except Exception:
        return False


def _roman(n: int) -> str:
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
            (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def _letters(n: int) -> str:
    # Word repeats the letter: a..z, aa..zz
    return chr(ord("a") + (n - 1) % 26) * ((n - 1) // 26 + 1)


def fmt_number(n: int, style: int) -> str:
    if style == 1:
        return _roman(n).upper()
    if style == 2:
        return _roman(n)
    if style == 3:
        return _letters(n).upper()
    if style == 4:
        return _letters(n)
    return str(n)


def _note_numbers(coll) -> dict[int, str]:
    out: dict[int, str] = {}
    try:
        count = coll.Count
    except Exception:
        return out
    if not count:
        return out
    try:
        rule, start, style = coll.NumberingRule, coll.StartingNumber, coll.NumberStyle
    except Exception:
        rule, start, style = 0, 1, 0
    counter = start - 1
    prev = None
    for k in range(1, count + 1):
        ref = coll.Item(k).Reference
        if rule == 1:
            cur = ref.Information(WD_SECTION)
        elif rule == 2:
            cur = ref.Information(WD_PAGE)
        else:
            cur = None
        if rule in (1, 2) and cur != prev:
            counter = start - 1
            prev = cur
        counter += 1
        out[k] = fmt_number(counter, style if style in (0, 1, 2, 3, 4) else 0)
    return out


def _page_label(rng, fallback_rng=None) -> str:
    n = rng.Information(WD_ADJ_PAGE)
    style = 0
    for r in (rng, fallback_rng):
        if r is None:
            continue
        try:
            style = r.Sections.Item(1).Footers.Item(1).PageNumbers.NumberStyle
            break
        except Exception:
            continue
    return fmt_number(int(n), style)


def _n_suffix(nums: list[str]) -> str:
    uniq = []
    for x in nums:
        if x not in uniq:
            uniq.append(x)
    if len(uniq) == 1:
        return "n" + uniq[0]
    if all(x.isdigit() for x in uniq):
        ints = sorted(int(x) for x in uniq)
        if ints == list(range(ints[0], ints[-1] + 1)):
            return f"nn{ints[0]}–{ints[-1]}"
        return "nn" + ", ".join(str(i) for i in ints)
    return "nn" + ", ".join(uniq)


def paginate(path: Path, occs, opts, log=print, final_path: Path | None = None) -> list[str]:
    """Update fields, read pages and note numbers, and (for the highlight/auto
    note modes) save a finalized plain-text-index copy to `final_path`.

    The file at `path` keeps a live, updated index either way.
    Returns messages for the user (e.g. locators that need a manual check).
    """
    import pythoncom
    import win32com.client

    msgs: list[str] = []
    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    doc = None
    try:
        word.Visible = False
        word.DisplayAlerts = WD_ALERTS_NONE
        try:
            word.Options.PrintHiddenText = False
        except Exception:
            pass
        doc = word.Documents.Open(str(Path(path).resolve()), False, False, False)
        try:
            view = doc.ActiveWindow.View
            view.Type = WD_PRINT_VIEW          # page numbers of note text need Print Layout
            view.ShowAll = False
            view.ShowHiddenText = False
            view.ShowFieldCodes = False
        except Exception:
            pass
        doc.Bookmarks.ShowHidden = True
        log("Updating fields (tables of contents and the index)…")
        doc.Repaginate()
        doc.Fields.Update()
        try:
            for i in range(1, doc.TablesOfContents.Count + 1):
                doc.TablesOfContents.Item(i).Update()
            for i in range(1, doc.Indexes.Count + 1):
                doc.Indexes.Item(i).Update()
        except Exception:
            pass
        doc.Repaginate()

        log("Reading page and note numbers…")
        fn_nums = _note_numbers(doc.Footnotes)
        en_nums = _note_numbers(doc.Endnotes)
        for o in occs:
            if o.in_note and o.note_ordinal:
                table = fn_nums if o.note_kind == "footnote" else en_nums
                o.note_number = table.get(o.note_ordinal)
            if not o.bookmark:
                continue
            ref_rng = None
            if o.in_note and o.note_ordinal:
                try:
                    coll = doc.Footnotes if o.note_kind == "footnote" else doc.Endnotes
                    ref_rng = coll.Item(o.note_ordinal).Reference
                except Exception:
                    ref_rng = None
            try:
                if doc.Bookmarks.Exists(o.bookmark):
                    o.page = _page_label(doc.Bookmarks.Item(o.bookmark).Range, ref_rng)
                elif ref_rng is not None:
                    o.page = _page_label(ref_rng)
            except Exception:
                if ref_rng is not None:
                    try:
                        o.page = _page_label(ref_rng)
                    except Exception:
                        pass

        # Word's own index is the authority for where note references fell:
        # read it back and match each marked page number to its note.
        marker = {"italic": "Italic", "highlight": "Italic", "auto": "Italic", "bold": "Bold"}.get(
            opts.footnote_mode)
        fields = _index_fields(doc)
        if fields and marker:
            note_occs = [o for o in occs if o.bookmark and o.in_note]
            names = {o.ref.book_name for o in occs if o.ref and getattr(o, "is_scripture", True)}
            results = _match_fields(doc, fields, opts.separator, marker, note_occs, names)
            for fld, entries, assign, unmatched in results:
                for (ei, li), group in assign.items():
                    for o in group:
                        o.page = entries[ei]["locs"][li]["text"]
            _flag_merged(note_occs, [r[2] for r in results])
            doc.Save()                      # live copy with the index built
            log("Saved the copy with a live, updated index.")
            if opts.footnote_mode in ("highlight", "auto") and final_path is not None:
                n_done, flagged = _finalize_all(doc, results, opts.footnote_mode, marker)
                _save_as(doc, final_path)
                if opts.footnote_mode == "auto":
                    log(f"Added note numbers to {n_done} page numbers.")
                    if flagged:
                        msgs.append("Highlighted for a manual check (the note could not be matched "
                                    "with certainty): " + "; ".join(flagged))
                else:
                    log(f"Highlighted {n_done} note page numbers.")
                log(f"Saved the finalized copy (plain-text index): {Path(final_path).name}")
        else:
            doc.Save()
            log("Saved the copy with a live, updated index.")
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        try:
            word.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()
    return msgs


def _save_as(doc, path):
    p = str(Path(path).resolve())
    try:
        doc.SaveAs2(p, 16)          # wdFormatDocumentDefault (.docx)
    except Exception:
        doc.SaveAs(p, 16)


def _index_fields(doc) -> list:
    """All INDEX fields in the main story, in document order."""
    out = []
    for i in range(1, doc.Fields.Count + 1):
        f = doc.Fields.Item(i)
        if f.Type == WD_FIELD_INDEX:
            out.append(f)
    return out


def all_book_names() -> set:
    """Every book heading the index could contain: built-in names in all
    languages, the user's renamed books, and custom books."""
    names = set(ENGLISH_FALLBACK.values())
    for p in PROFILES.values():
        names |= set(p.get("names", {}).values())
    try:
        from . import settings as SET
        s = SET.load()
        for cb in s.get("custom_books", []):
            names.add(cb.get("name", ""))
        for ls in s.get("languages", {}).values():
            names |= set(ls.get("names", {}).values())
    except Exception:
        pass
    return names


SCRIPTURE_LETTERS = {None, "", "O", "A", "N", "X", "S", "I"}


def parse_letter(code: str) -> str | None:
    m = re.search(r'\\f\s+"?([^"\s]*)"?', code or "")
    return (m.group(1).upper() or None) if m else None


def _match_fields(doc, fields, sep, marker, note_occs, extra_names, mark_by_page=None):
    """Read every INDEX field and pair its marked page numbers with notes.

    Scripture indexes (no \\f letter, or O/A/N/X/S) are read as book headings
    with references under them; word and term indexes as headings with
    optional subentries."""
    results = []
    for fld in fields:
        try:
            code = fld.Code.Text
        except Exception:
            code = ""
        fsep = parse_separator(code) if code else sep
        letter = parse_letter(code)
        f_occs = [o for o in note_occs if (getattr(o, "letter", None) or None) == letter]
        if letter in SCRIPTURE_LETTERS:
            entries = _read_index(doc, fld, fsep or sep, marker, extra_books=extra_names)
        else:
            entries = _read_term_index(doc, fld, fsep or sep, marker)
        note_occs_f = f_occs
        if mark_by_page is not None:
            for e in entries:
                for loc in e["locs"]:
                    loc["marked"] = (e["book"], e["entry"], loc["text"]) in mark_by_page
        assign, unmatched = match_note_locators(entries, note_occs_f)
        results.append((fld, entries, assign, unmatched))
    return results


PAGE_TOKEN = re.compile(r"[0-9ivxlcdmIVXLCDM]+(?:[–-][0-9ivxlcdmIVXLCDM]+)?")


def _read_term_index(doc, fld, sep: str, marker: str | None) -> list[dict]:
    """Parse a word or term index: level-1 headings (with or without page
    numbers) and level-2 subentries, told apart by their left indent."""
    paras = fld.Result.Paragraphs
    rows = []
    for i in range(1, paras.Count + 1):
        item = paras.Item(i)
        prng = item.Range
        text = prng.Text.rstrip("\r\x07\x0c")
        try:
            left = float(prng.ParagraphFormat.LeftIndent)
        except Exception:
            left = None
        rows.append((i, prng, text, left))
    lefts = [r[3] for r in rows if r[3] is not None and r[2].strip()]
    base = min(lefts) if lefts else None
    entries = []
    current = None
    for i, prng, text, left in rows:
        if not text.strip():
            continue
        top = left is None or base is None or left <= base + 1
        if sep not in text:
            if top:
                current = text
            continue
        head, locs = text.split(sep, 1)
        if top:
            book, entry = head, ""
            current = head
        else:
            book, entry = current, head
        base_off = len(head) + len(sep)
        items = []
        for m in re.finditer(r"[^,\s]+", locs):
            tok = m.group().rstrip(".;")
            if not PAGE_TOKEN.fullmatch(tok):
                continue
            start = prng.Start + base_off + m.start()
            lr = doc.Range(start, start + len(tok))
            val = getattr(lr.Font, marker) if marker else 0
            items.append({"text": tok, "offset": base_off + m.start(), "marked": val in (True, -1)})
        entries.append({"para": i, "book": book, "entry": entry, "locs": items})
    return entries


def _finalize_all(doc, results, mode, marker):
    done, flagged = 0, []
    for fld, entries, assign, unmatched in reversed(results):
        d, f = _finalize(doc, fld, entries, assign, unmatched, mode, marker)
        done += d
        flagged = f + flagged
    return done, flagged


def _read_index(doc, fld, sep: str, marker: str | None, extra_books=()) -> list[dict]:
    """Parse the generated index into entries with their page-number tokens."""
    books = all_book_names() | set(extra_books)
    paras = fld.Result.Paragraphs
    entries = []
    current = None
    for i in range(1, paras.Count + 1):
        prng = paras.Item(i).Range
        text = prng.Text.rstrip("\r\x07\x0c")
        if text in books:
            current = text
            continue
        if current is None or sep not in text:
            continue
        entry, locs = text.split(sep, 1)
        base = len(entry) + len(sep)
        items = []
        for m in re.finditer(r"[^,\s]+", locs):
            start = prng.Start + base + m.start()
            lr = doc.Range(start, start + len(m.group()))
            val = getattr(lr.Font, marker) if marker else 0
            items.append({"text": m.group(), "offset": base + m.start(), "marked": val in (True, -1)})
        entries.append({"para": i, "book": current, "entry": entry, "locs": items})
    return entries


def match_note_locators(entries: list[dict], note_occs) -> tuple[dict, list]:
    """Pair each marked (note) page number in the index with the note
    reference(s) it stands for.

    Notes come in document order, and so do page numbers, so when an entry has
    as many marked page numbers as note references they pair one-to-one.  When
    counts differ (two notes on one page, or a note on the same page as a body
    reference) the computed page decides, and anything still uncertain is
    returned in `unmatched`.
    """
    by_key: dict[tuple, list] = {}
    for o in note_occs:
        by_key.setdefault((o.ref.book_name, o.ref.label()), []).append(o)
    assign: dict[tuple, list] = {}
    unmatched: list[tuple] = []
    for ei, e in enumerate(entries):
        marked = [li for li, loc in enumerate(e["locs"]) if loc["marked"]]
        if not marked:
            continue
        notes = list(by_key.get((e["book"], e["entry"]), []))
        if len(marked) == len(notes):
            for li, o in zip(marked, notes):
                assign[(ei, li)] = [o]
            continue
        remaining = list(notes)
        left = []
        for li in marked:
            page = e["locs"][li]["text"]
            grp = [o for o in remaining if o.page == page]
            if grp:
                assign[(ei, li)] = grp
                remaining = [o for o in remaining if o not in grp]
            else:
                left.append(li)
        if left and len(left) == len(remaining):
            for li, o in zip(left, remaining):
                assign[(ei, li)] = [o]
            left = []
        for li in left:
            unmatched.append((ei, li))
    return assign, unmatched


def _flag_merged(note_occs, assigns):
    used = {id(o) for assign in assigns for grp in assign.values() for o in grp}
    for o in note_occs:
        if id(o) in used:
            continue
        o.merged_warning = ("not matched to a page number in the index; probably on the same page "
                            "as a body reference to the same passage")


def _finalize(doc, fld, entries, assign, unmatched, mode, marker: str | None = "Italic"):
    """Edit the index text (bottom-up so offsets stay valid), then unlink it."""
    paras = fld.Result.Paragraphs
    unmatched_set = set(unmatched)
    done = 0
    flagged = []
    for ei in range(len(entries) - 1, -1, -1):
        e = entries[ei]
        prng = paras.Item(e["para"]).Range
        for li in range(len(e["locs"]) - 1, -1, -1):
            loc = e["locs"][li]
            if not loc["marked"]:
                continue
            s = prng.Start + loc["offset"]
            lr = doc.Range(s, s + len(loc["text"]))
            if lr.Text != loc["text"]:
                continue
            if marker:
                setattr(lr.Font, marker, False)
            if mode == "auto" and (ei, li) in assign and (ei, li) not in unmatched_set:
                nums = [o.note_number or str(o.note_ordinal) for o in assign[(ei, li)]]
                lr.InsertAfter(_n_suffix(nums))
                done += 1
            else:
                lr.HighlightColorIndex = WD_YELLOW
                if mode == "auto":
                    flagged.append(f"{e['book']} {e['entry']}, p. {loc['text']}")
                else:
                    done += 1
    fld.Unlink()
    return done, list(reversed(flagged))


# ---------------------------------------------------------------------------
# Static copy from an already-checked indexed document
# ---------------------------------------------------------------------------
class _RefKey:
    def __init__(self, book: str, label: str):
        self.book_name = book
        self._label = label

    def label(self) -> str:
        return self._label


class NoteEntry:
    """An XE field found inside a footnote or endnote."""

    def __init__(self, book, label, page, note_number, note_ordinal, kind, switches, letter=None):
        self.letter = letter
        self.ref = _RefKey(book, label)
        self.page = page
        self.note_number = note_number
        self.note_ordinal = note_ordinal
        self.note_kind = kind
        self.switches = switches
        self.merged_warning = ""


XE_RE = re.compile(r'XE\s+"((?:[^"\\]|\\.)*)"(.*)$', re.S)


def parse_xe(code: str):
    """An XE field code -> (heading or book, subentry or reference, switches, \\f letter)."""
    m = XE_RE.search(code or "")
    if not m:
        return None
    levels = re.split(r"(?<!\\):", m.group(1))
    book = levels[0].replace("\\:", ":").strip()
    label = levels[1].replace("\\:", ":").strip() if len(levels) > 1 else ""
    rest = re.sub(r'"(?:[^"\\]|\\.)*"', "", m.group(2))
    switches = set(re.findall(r"\\([bi])\b", rest))
    if re.search(r"\\t\b", rest):
        switches.add("t")
    return book, label, switches, parse_letter(m.group(2))


def parse_separator(index_code: str) -> str:
    m = re.search(r'\\e\s+"([^"]*)"', index_code or "")
    return m.group(1) if m else ", "


def make_static_copy(path: Path, out_path: Path, mode: str = "auto", marker: str = "auto",
                     update_first: bool = False, log=print) -> list[str]:
    """Open an indexed document read-only, turn its live index into plain text with
    note locators completed ("33n12") or highlighted, and save it as `out_path`.

    The index entry (XE) fields in the text are left in place.
    `marker`: "auto" (from the XE switches), "Bold", "Italic", or "none" (match by page).
    """
    import pythoncom
    import win32com.client

    msgs: list[str] = []
    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    doc = None
    try:
        word.Visible = False
        word.DisplayAlerts = WD_ALERTS_NONE
        doc = word.Documents.Open(str(Path(path).resolve()), False, True, False)   # read-only
        try:
            view = doc.ActiveWindow.View
            view.Type = WD_PRINT_VIEW
            view.ShowAll = False
            view.ShowHiddenText = False
            view.ShowFieldCodes = False
        except Exception:
            pass
        doc.Repaginate()
        if update_first:
            log("Updating the index from the document…")
            doc.Fields.Update()
            for i in range(1, doc.Indexes.Count + 1):
                doc.Indexes.Item(i).Update()
            doc.Repaginate()
        fields = _index_fields(doc)
        if not fields:
            raise RuntimeError("No live index (INDEX field) was found. If the index has already been "
                               "converted to text, this copy is already static.")
        sep = parse_separator(fields[0].Code.Text)

        log("Reading index entries in notes…")
        notes: list[NoteEntry] = []
        for kind, coll in (("footnote", doc.Footnotes), ("endnote", doc.Endnotes)):
            nums = _note_numbers(coll)
            for k in range(1, coll.Count + 1):
                note = coll.Item(k)
                flds = note.Range.Fields
                for j in range(1, flds.Count + 1):
                    f = flds.Item(j)
                    if f.Type != WD_FIELD_INDEX_ENTRY:
                        continue
                    parsed = parse_xe(f.Code.Text)
                    if not parsed or "t" in parsed[2]:
                        continue
                    if parsed[3] in SCRIPTURE_LETTERS and not parsed[1]:
                        continue
                    try:
                        page = _page_label(f.Code, note.Reference)
                    except Exception:
                        page = None
                    notes.append(NoteEntry(parsed[0], parsed[1], page, nums.get(k), k, kind, parsed[2],
                                           parsed[3]))
        if not notes:
            raise RuntimeError("No index entries were found inside footnotes or endnotes, so there are "
                               "no note page numbers to complete.")

        if marker == "auto":
            sw = [n.switches for n in notes]
            if all("b" in x for x in sw):
                marker = "Bold"
            elif all("i" in x for x in sw):
                marker = "Italic"
            else:
                marker = "none"
            log(f"Note page numbers are marked: {marker.lower() if marker != 'none' else 'not marked; matching by page'}.")
        attr = None if marker == "none" else marker

        want = None
        if attr is None:
            # nothing marks the note page numbers: mark the ones whose page matches a note
            want = {(n.ref.book_name, n.ref.label(), n.page) for n in notes}
        results = _match_fields(doc, fields, sep, attr, notes, {n.ref.book_name for n in notes}, want)
        assign_all = [r[2] for r in results]
        done, flagged = _finalize_all(doc, results, mode, attr)
        _save_as(doc, out_path)
        if mode == "auto":
            log(f"Added note numbers to {done} page numbers.")
            if flagged:
                msgs.append("Highlighted for a manual check (the note could not be matched with "
                            "certainty): " + "; ".join(flagged))
        else:
            log(f"Highlighted {done} note page numbers.")
        unused = [n for n in notes if not any(n in g for a in assign_all for g in a.values())]
        if unused:
            msgs.append(f"{len(unused)} note reference(s) share a page number with a body reference "
                        "to the same passage, so no separate n# was added: " +
                        "; ".join(f"{n.ref.book_name} {n.ref.label()} (note {n.note_number})" for n in unused))
        log(f"Saved {Path(out_path).name}")
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        try:
            word.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()
    return msgs
