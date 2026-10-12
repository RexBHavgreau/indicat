"""The PDF route: scan a PDF's text layer and build a static index from it.

The page numbers are the printed page numbers read from the PDF, and the note
numbers are those printed in its footnotes, so the index is complete when it is
written: Word is not needed.  The index is written as a Word document (.docx)
or an OpenDocument text (.odt).
"""
from __future__ import annotations

import time
from pathlib import Path

from . import pipeline as PL
from . import settings as SET
from . import terms as T
from .parser import INDEXED_STATUSES, Hit, Scanner
from .pdf_io import PdfBook, ocr_fix


def known_word_fn(lang, defs):
    """For rejoining words hyphenated at a line end: book names and the forms in term sets."""
    forms = set()
    for d in defs:
        if d.kind == "terms":
            for f, _ in T.compile_set(d).forms:
                for w in f.split():
                    forms.add(w)

    names = set()
    for key in lang.spellings:
        for w in key.split():
            if sum(c.isalpha() for c in w) >= 4:
                names.add(T.fold_str(w.rstrip(".")))

    def known(word: str) -> bool:
        if lang.resolve(word):
            return True
        f = T.fold_str(word.rstrip("."))
        return f in forms or f in names
    return known


def scan_pdf(path: str | Path, settings: dict | None = None, distant_after: int = 15,
             progress=None, log=print) -> PL.ScanResult:
    settings = settings if settings is not None else SET.load()
    cat, lang = SET.make_context(settings)
    msgs: list[str] = []
    defs = PL.active_defs(settings, None, msgs)
    t0 = time.time()
    book = PdfBook(path, known_word_fn(lang, defs), progress)
    log(f"Read {len(book.pages)} pages in {time.time() - t0:.0f} s.")
    if book.ocr:
        dropped = [d.short for d in defs if d.kind != "terms"]
        defs = [d for d in defs if d.kind == "terms"]
        if dropped:
            msgs.append("This PDF was OCR'd (its text lies over page images), so only the Scripture index and "
                        "term sets are built: OCR'd " + ", ".join(dropped) + " text is not reliable enough to index "
                        "word by word.")
    engine = T.TermEngine(settings, defs) if defs else None
    do_scripture = settings.get("scripture", True)
    sc = Scanner(lang, distant_after=distant_after, old_styles=True)
    occs: list[PL.Occurrence] = []
    seq = [0]
    do_bib = settings.get("index_bibliography", False)

    def add(seg, items, fixed=(), note_kind=None, note_ord=None):
        for h in items:
            page = book.page_of(seg, max(h.start, h.end - 1))      # where it ends, as Word does
            inter = next((it for it in seg.interrupts if it.start < h.end and h.start < it.end), None)
            ocr_hit = any(h.start <= k < h.end for k in fixed)
            bib = getattr(seg, "biblio", False) and not do_bib
            if isinstance(h, T.TermHit):
                uid = f"{h.index}|pdf:{seg.part}:{seg.idx}:{h.start}:{h.end}"
                status, inc, reason = h.status, h.status in PL.TERM_INDEXED, h.reason
                if bib:
                    status, inc = "bibliography", False
                if inter is not None:
                    status, inc = "interrupted", False
                    reason = _interrupt_reason(inter, lang)
                hit = Hit(h.start, h.end, None, status, reason, raw=seg.text[h.start:h.end])
                o = PL.Occurrence(uid, seq[0], seg.part, seg.idx, h.start, h.end, hit, h.ref, status, inc,
                                  book.snippet(seg, h.start, h.end), note_kind, note_ord,
                                  index=h.index, words=h.words or None)
            else:
                uid = f"pdf:{seg.part}:{seg.idx}:{h.start}:{h.end}"
                inc = PL.include_by_default(h.status, settings)
                if inter is not None:
                    h.status, inc = "interrupted", False
                    h.reason = _interrupt_reason(inter, lang)
                elif ocr_hit and h.status in INDEXED_STATUSES:
                    h.status = "ocr"
                    h.reason = "read through an OCR slip (l or I for 1, ; for :): check the page"
                if bib:
                    h.status, inc = "bibliography", False
                if h.status == "unknown-book" and h.reason and "?" not in h.reason:
                    import re
                    m = re.match(r"“(.+?)”", h.reason)
                    sug = lang.suggest(m.group(1)) if m else ""
                    if sug:
                        h.reason += f" — {m.group(1)} → {sug}"
                o = PL.Occurrence(uid, seq[0], seg.part, seg.idx, h.start, h.end, h, h.ref, h.status, inc,
                                  book.snippet(seg, h.start, h.end), note_kind, note_ord)
            o.page = book.label(page)
            o.pdf_page = page
            o.page_sort = (page,)
            if note_kind:
                o.note_number = seg.note_number
            occs.append(o)
            seq[0] += 1

    def merged(seg, hits):
        items = list(hits) if do_scripture else []
        if engine is not None:
            items.extend(engine.scan(seg.text, seg.meta()))
        items.sort(key=lambda h: (h.start, h.end))
        return items

    def prepare(seg):
        if book.ocr:
            seg.text, fixed = ocr_fix(seg.text)
            return fixed
        return []

    def scan_note(key, ctx):
        for ns in book.note_segments.get(key, []):
            fixed = prepare(ns)
            nh, _ = sc.scan_segment(ns.text, ns.italic, seg_no[0], ctx=ctx)
            add(ns, merged(ns, nh), fixed, ns.note_kind, book.note_ordinals.get(key))

    anchored = {a.note_id for s in book.body_segments for a in s.anchors}
    pending = sorted((k for k in book.note_segments if k not in anchored), key=lambda k: (k[0], _num(k[1])))
    seg_no = [0]
    for seg in book.body_segments:
        seg_no[0] = seg.idx
        if seg.heading:
            sc.heading()
        fixed = prepare(seg)
        hits, snaps = sc.scan_segment(seg.text, seg.italic, seg.idx, anchors=[a.offset for a in seg.anchors])
        items = merged(seg, hits)
        hi = 0
        for a in sorted(seg.anchors, key=lambda a: a.offset):
            before = [h for h in items[hi:] if h.start < a.offset]
            add(seg, before, fixed)
            hi += len(before)
            scan_note(a.note_id, snaps.get(a.offset, sc.ctx).copy())
        add(seg, items[hi:], fixed)
        # notes whose mark wasn't found in the text: read them at the end of their page
        last_page = seg.pages[-1] if seg.pages else -1
        while pending and pending[0][0] <= last_page:
            scan_note(pending.pop(0), sc.ctx.copy())
    while pending:
        scan_note(pending.pop(0), sc.ctx.copy())

    word_ids = {d.id for d in defs if d.kind in ("script", "lang")}
    refs = []
    for o in occs:
        if o.index in word_ids:
            if o.ref is not None:
                refs.append(o.ref)
            for _, _, r in o.words or []:
                refs.append(r)
    T.choose_headings(refs)

    warnings = list(book.warnings) + msgs + list(lang.conflicts)
    if book.skipped_index:
        warnings.append(f"The book's own index (from p. {book.skipped_index}) was left out of the scan.")
    flagged = book.flagged_pages()
    if flagged:
        warnings.append("Pages to check (text missing, scant or garbled): " +
                        "; ".join(f"p. {p.label} (PDF page {p.index + 1}): {p.flag}" for p in flagged[:30]) +
                        (f"; and {len(flagged) - 30} more" if len(flagged) > 30 else ""))
    guessed = [p for p in book.pages if p.label_source == "index"]
    if guessed and len(guessed) > 0.5 * len(book.pages):
        warnings.append("No printed page numbers were found in the PDF, so PDF page numbers are used. "
                        "Check the page numbers before printing the index.")
    res = PL.ScanResult(Path(path), occs, warnings, 0, 0, len(book.note_segments), settings, cat, lang, defs,
                        do_scripture)
    res.pdf = book
    res.kind = "pdf"
    return res


def _num(s):
    return int(s) if str(s).isdigit() else 0


def _interrupt_reason(it, lang) -> str:
    sug = it.joined if (lang.resolve(it.joined) or lang.resolve(it.joined + ".")) else ""
    return f"possible interrupted term: {it.display}" + (f" → {sug}?" if sug else "")


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------
def output_names(stem: str, out_dir: Path, fmt: str) -> dict:
    return {"index": out_dir / f"{stem} - Index.{fmt}",
            "proof": out_dir / f"{stem} - Index Proof List.docx",
            "csv": out_dir / f"{stem} - Index Proof List.csv"}


def build_pdf(res: PL.ScanResult, opts: PL.BuildOptions, fmt: str = "docx", log=print) -> PL.BuildResult:
    from . import static_index as SI
    from . import proof as P
    opts.out_dir.mkdir(parents=True, exist_ok=True)
    names = output_names(res.path.stem, opts.out_dir, fmt)
    occs = PL._expand_quotations(sorted(res.occurrences, key=lambda o: o.seq))
    for o in occs:
        if o.ref is not None:
            o.ref.cat = res.catalog
    msgs: list[str] = []
    model = SI.build_model(res, occs, opts)
    font = res.pdf.font_name or "Times New Roman"
    if PL.font_installed(font) is False:
        msgs.append(f"The book's font (“{font}”) isn't installed on this computer, so the index is set in "
                    "Times New Roman. Change the font of the index styles to match the book.")
        font = "Times New Roman"
    if fmt == "odt":
        SI.write_odt(names["index"], model, opts, font)
    else:
        SI.write_docx(names["index"], model, opts, font)
    log(f"Saved {names['index'].name}")
    P.write_proof(names["proof"], names["csv"], res.path, occs, opts, True, msgs + list(res.warnings), res,
                  page_source="read from the printed page numbers in the PDF")
    log(f"Saved {names['proof'].name}")
    out = PL.BuildResult(names["index"], names["proof"], names["csv"], False, msgs)
    return out
