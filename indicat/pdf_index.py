"""The PDF route: scan a PDF's text layer and build a static index from it.

The page numbers are the printed page numbers read from the PDF, and the note
numbers are those printed in its footnotes, so the index is complete when it is
written: Word is not needed.  The index is written as a Word document (.docx)
or an OpenDocument text (.odt).
"""
from __future__ import annotations

import re
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


# ---------------------------------------------------------------------------
# The pages to index (PDF page numbers: 1 = the PDF's first page)
# ---------------------------------------------------------------------------
_RANGE_RE = re.compile(r"^(\d+)\s*(?:(?:[-–—]|to)\s*(\d+)?)?$", re.I)


def parse_pages(text: str, n_pages: int | None = None) -> list[tuple[int, int]]:
    """"9–14, 21–880" -> [(9, 14), (21, 880)] (PDF page numbers, 1-based, inclusive).  "21–" runs to
    the last page.  Blank -> [] (the whole PDF).  Raises ValueError with a message for the user."""
    out = []
    for part in re.split(r"[,;]", text or ""):
        part = part.strip()
        if not part:
            continue
        m = _RANGE_RE.match(part)
        if not m:
            raise ValueError(f"“{part}” isn't a page or a range. Type PDF page numbers, such as 9–880 or "
                             "9–14, 21–880.")
        a = int(m.group(1))
        if m.group(2):
            b = int(m.group(2))
        elif re.search(r"[-–—]|to", part, re.I):
            if n_pages is None:
                raise ValueError(f"“{part}”: give the last page too, such as {a}–{a + 99}.")
            b = n_pages
        else:
            b = a
        if a < 1 or b < a:
            raise ValueError(f"“{part}”: the first page must be 1 or more, and not after the last.")
        if n_pages is not None and b > n_pages:
            raise ValueError(f"“{part}”: the PDF has {n_pages} pages.")
        out.append((a, b))
    return sorted(out)


def pages_text(ranges: list[tuple[int, int]]) -> str:
    return ", ".join(str(a) if a == b else f"{a}–{b}" for a, b in ranges)


def page_key(path: str | Path) -> str:
    """How a PDF's page range is kept in the settings."""
    try:
        return str(Path(path).resolve()).lower()
    except OSError:
        return str(path).lower()


def stored_pages(settings: dict, path: str | Path) -> str:
    return (settings.get("pdf_pages") or {}).get(page_key(path), "")


def pdf_info(path: str | Path) -> tuple[int, list[str] | None]:
    """(number of pages, the PDF's own page labels or None), quickly, without reading the text."""
    from pypdf import PdfReader
    r = PdfReader(str(path))
    labels = None
    try:
        if "/PageLabels" in r.trailer["/Root"]:
            labels = list(r.page_labels)
    except Exception:
        labels = None
    return len(r.pages), labels


def describe_pages(text: str, n_pages: int, labels: list[str] | None) -> str:
    """What a page range covers, for the window: "872 of 900 pages = printed xi–862".  Raises
    ValueError for a range that can't be read."""
    ranges = parse_pages(text, n_pages)
    if not ranges:
        return f"Blank: all {n_pages} pages."
    count = sum(b - a + 1 for a, b in ranges)
    if labels and len(labels) == n_pages:
        return f"{count} of {n_pages} pages = printed pages {printed_span(labels, ranges)}."
    return f"{count} of {n_pages} pages. The printed page numbers they cover are shown in the log after the scan."


def printed_span(labels: list[str], ranges: list[tuple[int, int]]) -> str:
    """The printed page numbers a range covers: "xi–862" ("PDF pages 9–880 = printed xi–862")."""
    parts = []
    for a, b in ranges:
        la, lb = labels[a - 1], labels[b - 1]
        parts.append(la if a == b else f"{la}–{lb}")
    return ", ".join(parts)


def scan_pdf(path: str | Path, settings: dict | None = None, distant_after: int = 15,
             progress=None, log=print, pages: str | None = None) -> PL.ScanResult:
    """`pages`: the PDF pages to index ("9–14, 21–880"); None = the range kept for this PDF in the
    settings; blank = all.  Every page is still read (folios, running heads and notes that run on
    need the whole book), but only references on the chosen pages are kept."""
    settings = settings if settings is not None else SET.load()
    if pages is None:
        pages = stored_pages(settings, path)
    cat, lang = SET.make_context(settings)
    msgs: list[str] = []
    defs = PL.active_defs(settings, None, msgs)
    t0 = time.time()
    book = PdfBook(path, known_word_fn(lang, defs),
                   (lambda d, n: progress(0.8 * d / max(1, n), "Reading the PDF")) if progress else None)
    log(f"Read {len(book.pages)} pages in {time.time() - t0:.0f} s.")
    ranges = parse_pages(pages, len(book.pages))
    keep = None
    if ranges:
        keep = {i - 1 for a, b in ranges for i in range(a, b + 1)}
        labels = [book.label(i) for i in range(len(book.pages))]
        note = (f"Only PDF pages {pages_text(ranges)} were indexed (printed pages "
                f"{printed_span(labels, ranges)}; {len(keep)} of {len(book.pages)} pages).")
        log(note)
        msgs.append(note)
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
            if keep is not None and page not in keep:
                continue
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
        if progress and seg.idx % 50 == 0:
            progress(0.8 + 0.2 * seg.idx / max(1, len(book.body_segments)), "Scanning")
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
    flagged = [p for p in book.flagged_pages() if keep is None or p.index in keep]
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


def build_pdf(res: PL.ScanResult, opts: PL.BuildOptions, fmt: str = "docx", log=print,
              progress=None) -> PL.BuildResult:
    progress = progress or (lambda f, t="": None)
    progress(0.1, "Building the index")
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
    settings = opts.settings if opts.settings is not None else res.settings
    template = None
    if fmt != "odt":
        template, note = SI.template_for(settings)
        if note:
            msgs.append(note)
    font = res.pdf.font_name or "Times New Roman"
    if template is not None and settings.get("index_font", "body") == "styles":
        font = None                          # the template's index styles keep their font
    elif PL.font_installed(font) is False:
        msgs.append(f"The book's font (“{font}”) isn't installed on this computer, so the index is set in "
                    "Times New Roman. Change the font of the index styles to match the book.")
        font = "Times New Roman"
    if fmt == "odt":
        SI.write_odt(names["index"], model, opts, font)
    else:
        msgs.extend(SI.write_docx(names["index"], model, opts, font, template))
        log(f"Template: {template.name if template else 'Indicat’s plain style'}.")
    log(f"Saved {names['index'].name}")
    progress(0.7, "Writing the proofreading list")
    P.write_proof(names["proof"], names["csv"], res.path, occs, opts, True, msgs + list(res.warnings), res,
                  page_source="read from the printed page numbers in the PDF")
    log(f"Saved {names['proof'].name}")
    progress(1.0, "Done")
    return PL.BuildResult(names["index"], names["proof"], names["csv"], False, msgs)
