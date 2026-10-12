"""Scan and build: the engine behind both the GUI and the command line."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import docx_io as D
from . import settings as SET
from . import terms as T
from .parser import INDEXED_STATUSES, STATUS_LABELS, Hit, Ref, Scanner

FOOTNOTE_MODES = {
    "skip": "Don't index references in notes",
    "italic": "Index them, with their page numbers in italics",
    "bold": "Index them, with their page numbers in bold",
    "highlight": "Index them and highlight their page numbers, so n# can be added by hand",
    "auto": "Index them and add the note number automatically (e.g. 33n12)",
}
LIVE_MODES = ("skip", "italic", "bold")
FINAL_MODES = ("highlight", "auto")
NEEDS_WORD = set(FINAL_MODES)

# Page number separation: key -> (menu label, \e text, right-tab leader or None)
SEPARATORS = {
    "comma": ("Comma and space   (1:28, 54)", ", ", None),
    "tab_none": ("Right-aligned, no leader   (1:28        54)", "\t", "none"),
    "tab_dot": ("Right-aligned, dot leader   (1:28 ...... 54)", "\t", "dot"),
    "em_space": ("Em space   (1:28\u200354)", "\u2003", None),
    "en_space": ("En space   (1:28\u200254)", "\u2002", None),
    "space": ("Word space   (1:28 54)", " ", None),
    "em_dash_spaced": ("Spaced em dash   (1:28 \u2014 54)", " \u2014 ", None),
    "em_dash": ("Em dash   (1:28\u201454)", "\u2014", None),
    "en_dash_spaced": ("Spaced en dash   (1:28 \u2013 54)", " \u2013 ", None),
    "custom": ("Custom…", None, None),
}


def check_custom_separator(text: str) -> str | None:
    """Return an error message, or None if Word's INDEX \\e switch can take it."""
    if not text:
        return "Type the separator to use."
    if len(text) > 5:
        return "Word allows at most five characters between an entry and its page numbers."
    if '"' in text or "\\" in text:
        return "The separator can't contain double quotes or backslashes."
    if any(ch.isdigit() for ch in text) or "," in text.strip():
        return "Digits and commas can't be used: they would be confused with page numbers."
    return None


TERM_LABELS = {"word": "Word", "word-check": "Word (check the dictionary form)", "term": "Term set match",
               "quotation": "Quotation (not indexed)",
               "bibliography": "Bibliography (not indexed)"}
# statuses whose reason is shown next to the label in the review list
SHOW_REASON = {"quotation", "unknown-book", "check-name", "f-end", "word-check"}


def include_by_default(status: str, settings: dict) -> bool:
    """Is a Scripture hit with this status indexed unless the user says otherwise?"""
    if status == "chapter-only":
        return bool(settings.get("whole_chapters"))
    if status == "mt":
        return settings.get("mt_mode", "label") != "exclude"
    return status in INDEXED_STATUSES
TERM_INDEXED = {"word", "word-check", "term"}


@dataclass
class Occurrence:
    uid: str
    seq: int                       # reading order
    part: str
    seg_idx: int
    start: int
    end: int
    hit: Hit
    ref: Ref | None
    status: str
    include: bool
    context: str                   # snippet with the reference between ⟦ ⟧
    note_kind: str | None = None
    note_ordinal: int | None = None
    edited: bool = False
    # filled in after Word pagination
    page: str | None = None
    page_sort: tuple = ()
    note_number: str | None = None
    bookmark: str | None = None
    merged_warning: str = ""
    index: str = "scripture"          # which index: "scripture" or an IndexDef id
    words: list | None = None         # quotation rows: [(start, end, TermRef)]
    letter: str | None = None         # XE \\f letter written for it

    @property
    def is_scripture(self) -> bool:
        return self.index == "scripture"

    @property
    def indexable(self) -> bool:
        """Can it be included? (has an entry, or is a quotation with words)"""
        return self.ref is not None or bool(self.words)

    @property
    def in_note(self) -> bool:
        return self.note_kind is not None

    @property
    def where(self) -> str:
        if not self.in_note:
            return "Body"
        label = "Footnote" if self.note_kind == "footnote" else "Endnote"
        num = self.note_number or f"#{self.note_ordinal}"
        return f"{label} {num}"

    @property
    def display(self) -> str:
        t = self.ref.display() if self.ref else self.hit.raw
        return t if len(t) <= 60 else t[:57] + "…"

    @property
    def open_ended(self) -> bool:
        """"34ff.": indexed, but marked so it can be checked."""
        r = self.ref
        return bool(r is not None and self.is_scripture and r.s1 in ("ff", "ss") and not r.c2
                    and self.status in INDEXED_STATUSES)

    @property
    def where_kind(self) -> str:
        """Body / Footnotes / Endnotes, for the Where filter."""
        return {"footnote": "Footnotes", "endnote": "Endnotes"}.get(self.note_kind or "", "Body")

    @property
    def status_label(self) -> str:
        s = STATUS_LABELS.get(self.status) or TERM_LABELS.get(self.status, self.status)
        if self.open_ended:
            s = "Open-ended (ff)" if self.ref.s1 in ("ff", "f") else "Open-ended (ss)"
        if self.hit.reason and self.status in SHOW_REASON:
            s += f" — {self.hit.reason}"
        if self.edited:
            s += " (edited)"
        return s


@dataclass
class ScanResult:
    path: Path
    occurrences: list[Occurrence]
    warnings: list[str]
    existing_xe: int
    existing_index: int
    note_count: int
    settings: dict = field(default_factory=dict)
    catalog: object = None
    language: object = None
    defs: list = field(default_factory=list)          # the extra indexes switched on
    scripture: bool = True

    def index_name(self, index_id: str) -> str:
        if index_id == "scripture":
            return "Scripture"
        for d in self.defs:
            if d.id == index_id:
                return d.short
        return index_id

    def counts(self) -> dict:
        c = {}
        for o in self.occurrences:
            c[o.status] = c.get(o.status, 0) + 1
        return c

    def notes_with_refs(self) -> int:
        return sum(1 for o in self.occurrences if o.in_note and o.include)


def _snippet(text: str, s: int, e: int, before: int = 70, after: int = 50) -> str:
    a = max(0, s - before)
    b = min(len(text), e + after)
    pre = ("…" if a > 0 else "") + text[a:s]
    post = text[e:b] + ("…" if b < len(text) else "")
    return (pre + "⟦" + text[s:e] + "⟧" + post).replace("\t", " ").replace("\n", " ")


def active_defs(settings: dict, pkg: D.DocxPackage | None = None, messages: list | None = None) -> list:
    """The extra indexes to build for this document."""
    defs = T.index_defs(settings, messages=messages)
    if pkg is None:
        return defs
    dl = (pkg.styles.default_lang or "").split("-")[0].lower()
    out = []
    for d in defs:
        if d.kind == "lang" and dl and d.opts.get("lang") == dl:
            if messages is not None:
                messages.append(f"The {d.short} word index is off: {d.short} is the document's own language, "
                                "so every word would be indexed. Use a term set for the words you want.")
            continue
        out.append(d)
    return out


def scan(path: str | Path, settings: dict | None = None,
         distant_after: int = 15, progress=None) -> tuple[ScanResult, D.DocxPackage]:
    """progress(fraction, text): optional, for a progress bar."""
    progress = progress or (lambda f, t="": None)
    settings = settings if settings is not None else SET.load()
    cat, lang = SET.make_context(settings)
    pkg = D.DocxPackage(path)
    sc = Scanner(lang, distant_after=distant_after)
    msgs: list[str] = []
    defs = active_defs(settings, pkg, msgs)
    engine = T.TermEngine(settings, defs) if defs else None
    do_scripture = settings.get("scripture", True)
    do_bib = settings.get("index_bibliography", False)
    occs: list[Occurrence] = []
    seq = 0

    def add(seg: D.Segment, items: list, note_kind=None, note_ord=None):
        """items: Scripture Hits and TermHits, in text order."""
        nonlocal seq
        for h in items:
            if isinstance(h, T.TermHit):
                uid = f"{h.index}|{seg.part}:{seg.idx}:{h.start}:{h.end}"
                inc = h.status in TERM_INDEXED
                if any(a <= h.start < b for a, b in seg.in_simple_field):
                    inc = False
                status = h.status
                if seg.biblio and not do_bib:
                    status, inc = "bibliography", False
                hit = Hit(h.start, h.end, None, status, h.reason, raw=seg.text[h.start:h.end])
                occs.append(Occurrence(uid, seq, seg.part, seg.idx, h.start, h.end, hit, h.ref, status,
                                       inc, _snippet(seg.text, h.start, h.end), note_kind, note_ord,
                                       index=h.index, words=h.words or None))
            else:
                uid = f"{seg.part}:{seg.idx}:{h.start}:{h.end}"
                inc = include_by_default(h.status, settings)
                # references inside simple fields (e.g. old-style hyperlinks) cannot take an XE
                if any(a <= h.start < b for a, b in seg.in_simple_field):
                    inc = False
                if h.status == "unknown-book" and h.reason and "?" not in h.reason:
                    m = re.match(r"“(.+?)”", h.reason)
                    sug = lang.suggest(m.group(1)) if m else ""
                    if sug:
                        h.reason += f" — {m.group(1)} → {sug}"
                if seg.biblio and not do_bib:
                    h.status, inc = "bibliography", False
                occs.append(Occurrence(uid, seq, seg.part, seg.idx, h.start, h.end, h, h.ref,
                                       h.status, inc, _snippet(seg.text, h.start, h.end),
                                       note_kind, note_ord))
            seq += 1

    def merged(seg, hits):
        items = list(hits) if do_scripture else []
        if engine is not None:
            items.extend(engine.scan(seg.text, seg.meta()))
        items.sort(key=lambda h: (h.start, h.end))
        return items

    nseg = max(1, len(pkg.body_segments))
    for si, seg in enumerate(pkg.body_segments):
        if si % 50 == 0:
            progress(si / nseg, "Scanning")
        if seg.heading:
            sc.heading()
        hits, snaps = sc.scan_segment(seg.text, seg.italic, seg.idx,
                                      anchors=[a.offset for a in seg.anchors])
        items = merged(seg, hits)
        # interleave: body hits before the anchor, then the note, then the rest
        anchor_list = sorted(seg.anchors, key=lambda a: a.offset)
        hi = 0
        for a in anchor_list:
            before = [h for h in items[hi:] if h.start < a.offset]
            add(seg, before)
            hi += len(before)
            key = (a.kind, a.note_id)
            nsegs = pkg.note_segments.get(key, [])
            ctx = snaps.get(a.offset, sc.ctx).copy()
            for ns in nsegs:
                nh, _ = sc.scan_segment(ns.text, ns.italic, seg.idx, ctx=ctx)
                add(ns, merged(ns, nh), a.kind, pkg.note_ordinals.get(key))
        add(seg, items[hi:])

    # one heading per group of word forms
    word_ids = {d.id for d in defs if d.kind in ("script", "lang")}
    refs = []
    for o in occs:
        if o.index in word_ids:
            if o.ref is not None:
                refs.append(o.ref)
            for _, _, r in o.words or []:
                refs.append(r)
    T.choose_headings(refs)

    warnings = list(pkg.warnings) + msgs
    if pkg.existing_xe:
        warnings.append(f"The document already contains {pkg.existing_xe} index entry (XE) fields. "
                        "Tick 'Remove existing index entries' unless you want to keep them.")
    if pkg.existing_index:
        warnings.append(f"The document already contains {pkg.existing_index} INDEX field(s). Delete the "
                        "old index before building, or it will be rebuilt from the new entries too.")
    warnings.extend(lang.conflicts)
    res = ScanResult(Path(path), occs, warnings, pkg.existing_xe, pkg.existing_index,
                     len(pkg.note_segments), settings, cat, lang, defs, do_scripture)
    return res, pkg


def find_text(pkg: D.DocxPackage, query: str, limit: int = 200) -> list[dict]:
    """Places where `query` occurs (body and notes), for Add reference."""
    out = []
    q = query.strip()
    if not q:
        return out
    segs = [(s, None, None) for s in pkg.body_segments]
    for (kind, nid), lst in pkg.note_segments.items():
        for s in lst:
            segs.append((s, kind, pkg.note_ordinals.get((kind, nid))))
    for seg, kind, ordn in segs:
        start = 0
        while True:
            i = seg.text.find(q, start)
            if i < 0:
                break
            out.append(dict(part=seg.part, seg_idx=seg.idx, start=i, end=i + len(q),
                            context=_snippet(seg.text, i, i + len(q)), note_kind=kind,
                            note_ordinal=ordn))
            start = i + len(q)
            if len(out) >= limit:
                return out
    return out


def manual_occurrence(res: ScanResult, place: dict, ref: Ref) -> Occurrence:
    """An occurrence typed in by the user at `place` (from find_text)."""
    uid = f"manual:{place['part']}:{place['seg_idx']}:{place['start']}:{place['end']}:{ref.sort_key()}"
    hit = Hit(place["start"], place["end"], ref, "manual", raw=ref.display())
    seq = max((o.seq for o in res.occurrences), default=0) + 1
    return Occurrence(uid, seq, place["part"], place["seg_idx"], place["start"], place["end"], hit, ref,
                      "manual", True, place["context"], place["note_kind"], place["note_ordinal"])


@dataclass
class BuildOptions:
    out_dir: Path
    heading: str = ""                 # blank = the language's index title
    columns: int = 2
    separator: str = ", "           # text Word puts between entry and page numbers
    leader: str | None = None       # "dot" / "none" for right-aligned (tab) separation
    new_page: bool = True
    footnote_mode: str = "italic"
    remove_existing_xe: bool = False
    use_word: bool = True
    settings: dict | None = None


@dataclass
class BuildResult:
    indexed_docx: Path
    proof_docx: Path
    csv_path: Path
    used_word: bool
    messages: list[str] = field(default_factory=list)
    final_docx: Path | None = None


def output_names(stem: str, out_dir: Path) -> dict:
    return {"indexed": out_dir / f"{stem} - Indexed.docx",
            "final": out_dir / f"{stem} - Indexed (final).docx",
            "proof": out_dir / f"{stem} - Index Proof List.docx",
            "csv": out_dir / f"{stem} - Index Proof List.csv"}


def _expand_quotations(occs: list[Occurrence]) -> list[Occurrence]:
    """An included quotation row becomes one row per word in it."""
    out = []
    for o in occs:
        if o.status == "quotation" and o.include and o.words:
            for k, (s, e, r) in enumerate(o.words):
                st = "word-check" if r.note else "word"
                hit = Hit(s, e, None, st, r.note or "from an included quotation", raw="")
                out.append(Occurrence(f"{o.uid}#{k}", o.seq, o.part, o.seg_idx, s, e, hit, r, st, True,
                                      o.context, o.note_kind, o.note_ordinal, edited=True,
                                      index=o.index))
        else:
            out.append(o)
    return out


def build(scan_res: ScanResult, opts: BuildOptions, log=print, progress=None) -> BuildResult:
    """Write the indexed copy, paginate with Word if possible, and write the proof list.

    The document is re-read from disk so the original file is never modified.
    """
    progress = progress or (lambda f, t="": None)
    src = scan_res.path
    progress(0.02, "Reading the manuscript")
    fresh, pkg = scan(src, opts.settings if opts.settings is not None else scan_res.settings,
                      progress=lambda f, t="": progress(0.02 + 0.2 * f, "Reading the manuscript"))
    cat = fresh.catalog
    decided = {o.uid: o for o in scan_res.occurrences}
    occs = []
    for o in fresh.occurrences:
        d = decided.get(o.uid)
        if d is not None:
            o.include, o.ref, o.edited = d.include, d.ref, d.edited
            if d.edited:
                o.status = d.status
        occs.append(o)
    # references added by hand
    for d in scan_res.occurrences:
        if d.uid.startswith("manual:") and d.include and d.ref is not None:
            d.ref.cat = cat
            occs.append(d)
    occs.sort(key=lambda o: o.seq)
    occs = _expand_quotations(occs)

    opts.out_dir.mkdir(parents=True, exist_ok=True)
    names = output_names(src.stem, opts.out_dir)
    out_docx = names["indexed"]
    final_docx = names["final"] if opts.footnote_mode in FINAL_MODES else None
    proof, csv_path = names["proof"], names["csv"]
    msgs: list[str] = []

    if opts.remove_existing_xe:
        n = D.remove_xe_fields(pkg)
        log(f"Removed {n} existing index entry fields.")

    defs = {d.id: d for d in fresh.defs}
    single_letter = "S" if (fresh.defs and cat.split == "single") else None
    switch = {"italic": "i", "bold": "b", "highlight": "i", "auto": "i"}.get(opts.footnote_mode)
    segs = {}
    for s_ in pkg.body_segments:
        segs[(s_.part, s_.idx)] = s_
    for lst in pkg.note_segments.values():
        for s_ in lst:
            segs[(s_.part, s_.idx)] = s_

    bm_id = pkg.max_bookmark_id() + 1000
    to_write = [o for o in occs if o.include and o.ref is not None
                and (o.is_scripture or o.index in defs)
                and not (o.in_note and opts.footnote_mode == "skip")]
    # insert from the end of each segment backwards so offsets stay valid
    to_write.sort(key=lambda o: (o.part, o.seg_idx, o.end), reverse=True)
    written = 0
    progress(0.25, "Placing index entries")
    for wi, o in enumerate(to_write):
        if wi % 200 == 0:
            progress(0.25 + 0.2 * wi / max(1, len(to_write)), "Placing index entries")
        seg = segs[(o.part, o.seg_idx)]
        o.ref.cat = cat
        if o.is_scripture:
            entry = f"{D.escape_entry(o.ref.book_name)}:{D.escape_entry(o.ref.label())}"
            yomi = f"{o.ref.book_key()}:{o.ref.sort_key()}"
            o.letter = cat.index_group(o.ref.book) or single_letter
        else:
            r = o.ref
            entry = D.escape_entry(r.heading) + (f":{D.escape_entry(r.sub)}" if r.sub else "")
            parts = r.yomi().split(":", 1) if r.sub else [r.yomi()]
            yomi = ":".join(D.escape_entry(x) for x in parts)
            o.letter = defs[o.index].letter
        o.bookmark = f"_SIB{bm_id:06d}"
        els = D.xe_elements(entry, yomi, switch if o.in_note else None, o.bookmark, bm_id, o.letter)
        bm_id += 1
        if D.insert_after_offset(seg, o.end, els):
            written += 1
        else:
            o.bookmark = None
            msgs.append(f"Could not place an index field for {o.display} ({o.where}); add it by hand.")
    log(f"Inserted {written} index entry fields.")

    settings = opts.settings if opts.settings is not None else scan_res.settings
    font = None
    if settings.get("index_font", "body") == "body":
        font = pkg.body_font()
    D.ensure_index_styles(pkg, opts.leader if opts.separator == "\t" else None, opts.columns, font)
    if font:
        D.set_index_heading_font(pkg, font)
        log(f"Index font: {font} (the body text font).")
    shown = font or pkg.styles.font(pkg.styles.id_for_name("index 1"))
    if shown and font_installed(shown) is False:
        msgs.append(f"The index is set in “{shown}”, which isn't installed on this computer, so Word will "
                    "show it in a substitute font (and page breaks may differ from the printer's).")
    used_groups = {o.letter for o in to_write if o.bookmark and o.is_scripture}
    groups = [(L, t) for L, t in cat.groups_in_order() if L in used_groups]
    see_words = T.SEE_WORDS.get(cat_lang(fresh), T.SEE_WORDS["en"])
    extra = []
    used_letters = {o.letter for o in to_write if o.bookmark and not o.is_scripture}
    for d in fresh.defs:
        xrefs = []
        if d.kind == "terms":
            grouped: dict = {}
            for ref, kind, target in T.compile_set(d).crossrefs:
                grouped.setdefault((ref.display(), kind), (ref, kind, []))[2].append(target)
            for ref, kind, targets in grouped.values():
                word = see_words[0] if kind == "see" else see_words[1]
                text = f"{word} {'; '.join(targets)}"
                entry = D.escape_entry(ref.heading) + (f":{D.escape_entry(ref.sub)}" if ref.sub else "")
                parts = ref.yomi().split(":", 1) if ref.sub else [ref.yomi()]
                xrefs.extend(D.xe_elements(entry, ":".join(D.escape_entry(x) for x in parts), None, None, None,
                                           d.letter, see=text.replace('"', "'"), see_italic=len(word)))
        if d.letter in used_letters or xrefs:
            extra.append((d.title, d.letter, xrefs))
        else:
            msgs.append(f"Nothing was indexed for “{d.title}”, so it was left out.")
    D.append_index(pkg, opts.heading or cat.index_title, opts.columns, opts.separator, opts.new_page,
                   groups, single_letter, extra, scripture=fresh.scripture)
    progress(0.5, "Saving the indexed copy")
    pkg.save(out_docx)
    log(f"Saved {out_docx.name}")

    used_word = False
    if opts.use_word:
        from . import word_com
        if word_com.available():
            try:
                log("Opening the copy in Word to update fields and read page numbers…")
                progress(None, "Word is laying out the pages and building the index")
                msgs.extend(word_com.paginate(out_docx, occs, opts, log, final_docx))
                used_word = True
            except Exception as exc:          # keep going without page numbers
                msgs.append(f"Word automation failed: {exc}. The index field is in place; open the "
                            "copy in Word and press Ctrl+A, then F9.")
                log(msgs[-1])
        else:
            msgs.append("Microsoft Word automation is not available on this computer, so page "
                        "numbers could not be read. Open the copy in Word and press Ctrl+A, then F9.")
    if not used_word and opts.footnote_mode in NEEDS_WORD:
        msgs.append("Note page numbers were set in italics instead of being highlighted/completed, "
                    "because that step needs Word.")
    if not (final_docx and final_docx.exists()):
        final_docx = None

    from . import proof as P
    progress(0.95, "Writing the proofreading list")
    P.write_proof(proof, csv_path, src, occs, opts, used_word, msgs, fresh)
    progress(1.0, "Done")
    log(f"Saved {proof.name}")
    return BuildResult(out_docx, proof, csv_path, used_word, msgs, final_docx)


def font_installed(name: str) -> bool | None:
    """Is a font installed?  None when it can't be told (not Windows)."""
    import sys
    if sys.platform != "win32" or not name:
        return None
    try:
        import winreg
    except Exception:
        return None
    want = name.lower()
    key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    found_any = False
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key) as k:
                i = 0
                while True:
                    try:
                        val = winreg.EnumValue(k, i)[0]
                    except OSError:
                        break
                    i += 1
                    found_any = True
                    base = re.sub(r"\s*\((?:TrueType|OpenType|VGA res)\)\s*$", "", val, flags=re.I).lower()
                    names = [x.strip() for x in base.split("&")]
                    if any(n == want or n.startswith(want + " ") and n[len(want) + 1:].split()[0] in
                           ("regular", "bold", "italic", "light", "medium", "semibold", "black", "condensed")
                           for n in names):
                        return True
        except OSError:
            continue
    return False if found_any else None


def cat_lang(res: ScanResult) -> str:
    return res.settings.get("language", "en")


def make_static(src: str | Path, out_dir: str | Path | None = None, mode: str = "auto",
                marker: str = "auto", update_first: bool = False, log=print) -> tuple[Path, list[str]]:
    """Save '<name> (static index).docx': the checked live index turned into plain
    text, with note page numbers completed (mode="auto") or highlighted."""
    from . import word_com
    if not word_com.available():
        raise RuntimeError("Making a static copy needs Microsoft Word on this computer.")
    src = Path(src)
    out_dir = Path(out_dir) if out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{src.stem} (static index).docx"
    n = 2
    while out.exists():
        out = out_dir / f"{src.stem} (static index {n}).docx"
        n += 1
    msgs = word_com.make_static_copy(src, out, mode, marker, update_first, log)
    return out, msgs
