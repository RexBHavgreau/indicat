"""Scan and build: the engine behind both the GUI and the command line."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import docx_io as D
from . import settings as SET
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
        return self.ref.display() if self.ref else self.hit.raw

    @property
    def status_label(self) -> str:
        s = STATUS_LABELS.get(self.status, self.status)
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


def scan(path: str | Path, settings: dict | None = None,
         distant_after: int = 15) -> tuple[ScanResult, D.DocxPackage]:
    settings = settings if settings is not None else SET.load()
    cat, lang = SET.make_context(settings)
    pkg = D.DocxPackage(path)
    sc = Scanner(lang, distant_after=distant_after)
    occs: list[Occurrence] = []
    seq = 0

    def add(seg: D.Segment, hits: list[Hit], note_kind=None, note_ord=None):
        nonlocal seq
        for h in hits:
            uid = f"{seg.part}:{seg.idx}:{h.start}:{h.end}"
            inc = h.status in INDEXED_STATUSES
            # references inside simple fields (e.g. old-style hyperlinks) cannot take an XE
            if any(a <= h.start < b for a, b in seg.in_simple_field):
                inc = False
            occs.append(Occurrence(uid, seq, seg.part, seg.idx, h.start, h.end, h, h.ref,
                                   h.status, inc, _snippet(seg.text, h.start, h.end),
                                   note_kind, note_ord))
            seq += 1

    for seg in pkg.body_segments:
        if seg.heading:
            sc.heading()
        hits, snaps = sc.scan_segment(seg.text, seg.italic, seg.idx,
                                      anchors=[a.offset for a in seg.anchors])
        # interleave: body hits before the anchor, then the note, then the rest
        anchor_list = sorted(seg.anchors, key=lambda a: a.offset)
        hi = 0
        for a in anchor_list:
            before = [h for h in hits[hi:] if h.start < a.offset]
            add(seg, before)
            hi += len(before)
            key = (a.kind, a.note_id)
            nsegs = pkg.note_segments.get(key, [])
            ctx = snaps.get(a.offset, sc.ctx).copy()
            for ns in nsegs:
                nh, _ = sc.scan_segment(ns.text, ns.italic, seg.idx, ctx=ctx)
                add(ns, nh, a.kind, pkg.note_ordinals.get(key))
        add(seg, hits[hi:])

    warnings = list(pkg.warnings)
    if pkg.existing_xe:
        warnings.append(f"The document already contains {pkg.existing_xe} index entry (XE) fields. "
                        "Tick 'Remove existing index entries' unless you want to keep them.")
    if pkg.existing_index:
        warnings.append(f"The document already contains {pkg.existing_index} INDEX field(s). Delete the "
                        "old index before building, or it will be rebuilt from the new entries too.")
    warnings.extend(lang.conflicts)
    res = ScanResult(Path(path), occs, warnings, pkg.existing_xe, pkg.existing_index,
                     len(pkg.note_segments), settings, cat, lang)
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


def build(scan_res: ScanResult, opts: BuildOptions, log=print) -> BuildResult:
    """Write the indexed copy, paginate with Word if possible, and write the proof list.

    The document is re-read from disk so the original file is never modified.
    """
    src = scan_res.path
    fresh, pkg = scan(src, opts.settings if opts.settings is not None else scan_res.settings)
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

    opts.out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    out_docx = opts.out_dir / f"{stem} - Scripture Index.docx"
    final_docx = (opts.out_dir / f"{stem} - Scripture Index (final).docx"
                  if opts.footnote_mode in FINAL_MODES else None)
    proof = opts.out_dir / f"{stem} - Scripture Index Proof List.docx"
    csv_path = opts.out_dir / f"{stem} - Scripture Index Proof List.csv"
    msgs: list[str] = []

    if opts.remove_existing_xe:
        n = D.remove_xe_fields(pkg)
        log(f"Removed {n} existing index entry fields.")

    switch = {"italic": "i", "bold": "b", "highlight": "i", "auto": "i"}.get(opts.footnote_mode)
    segs = {}
    for s in pkg.body_segments:
        segs[(s.part, s.idx)] = s
    for lst in pkg.note_segments.values():
        for s in lst:
            segs[(s.part, s.idx)] = s

    bm_id = pkg.max_bookmark_id() + 1000
    to_write = [o for o in occs if o.include and o.ref is not None
                and not (o.in_note and opts.footnote_mode == "skip")]
    # insert from the end of each segment backwards so offsets stay valid
    to_write.sort(key=lambda o: (o.part, o.seg_idx, o.end), reverse=True)
    written = 0
    for o in to_write:
        seg = segs[(o.part, o.seg_idx)]
        o.ref.cat = cat
        entry = f"{D.escape_entry(o.ref.book_name)}:{D.escape_entry(o.ref.label())}"
        yomi = f"{o.ref.book_key()}:{o.ref.sort_key()}"
        o.bookmark = f"_SIB{bm_id:06d}"
        els = D.xe_elements(entry, yomi, switch if o.in_note else None, o.bookmark, bm_id,
                            cat.index_group(o.ref.book))
        bm_id += 1
        if D.insert_after_offset(seg, o.end, els):
            written += 1
        else:
            o.bookmark = None
            msgs.append(f"Could not place an index field for {o.display} ({o.where}); add it by hand.")
    log(f"Inserted {written} index entry fields.")

    D.ensure_index_styles(pkg, opts.leader if opts.separator == "\t" else None, opts.columns)
    used_groups = {cat.index_group(o.ref.book) for o in to_write if o.bookmark}
    groups = [(L, t) for L, t in cat.groups_in_order() if L in used_groups]
    D.append_index(pkg, opts.heading or cat.index_title, opts.columns, opts.separator, opts.new_page,
                   groups)
    pkg.save(out_docx)
    log(f"Saved {out_docx.name}")

    used_word = False
    if opts.use_word:
        from . import word_com
        if word_com.available():
            try:
                log("Opening the copy in Word to update fields and read page numbers…")
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
    P.write_proof(proof, csv_path, src, occs, opts, used_word, msgs)
    log(f"Saved {proof.name}")
    return BuildResult(out_docx, proof, csv_path, used_word, msgs, final_docx)


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
