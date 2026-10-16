"""Read the text layer of a PDF (born-digital or OCR'd) for indexing.

The PDF route builds a *static* index: the page numbers are the printed page
numbers (folios) read from the PDF, so nothing has to be laid out again.

What this module works out, page by page:

* lines of text, from the characters' positions (Hebrew runs are put back in
  reading order; superscript note numbers in the text are taken out and kept
  as note anchors);
* running heads and folios, by position (top or bottom margin) and repetition
  (the margin holds a line on many pages); folios give the printed page numbers;
* footnotes, by type size (smaller than the body text), position (a block at
  the foot of the page), and a separator rule or note numbers;
* headings (larger type), paragraphs, and lines joined back together.  A word
  hyphenated at the end of a line is joined when the whole word is a known book
  name or term; a word hyphenated across a page break is joined for reading but
  flagged ("Deu-‖143‖teronomy") and not indexed;
* pages whose text is missing, scant or garbled compared with the rest of the
  book, and whether the PDF was OCR'd (text over page images).
"""
from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .docx_io import Segment
from .parser import roman_to_int, _int_to_roman

HEB_LETTER = re.compile("[א-תװ-״יִ-ﭏ]")
HEB_MARK = re.compile("[֑-ׇ]")
HYPHENS = "-­‐"
SENT_END = ".?!:;”’\")]"


@dataclass
class Char:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    italic: bool


@dataclass
class Line:
    page: int
    top: float
    bottom: float
    x0: float
    x1: float
    size: float                     # typical type size of the line
    text: str = ""
    italic: list = field(default_factory=list)
    sups: list = field(default_factory=list)      # [(offset in text, digits)]: superscript numbers taken out
    kind: str = "body"              # body | head | foot | note | heading
    lead_sup: str = ""              # a superscript number at the very start (a note's number)
    endnote: bool = False
    col: int = 0                    # 0 = across the page, 1 = left column, 2 = right column


@dataclass
class PageInfo:
    index: int                      # 0-based PDF page
    label: str = ""                 # printed page number
    label_source: str = ""          # folio | pdf | inferred | index
    chars: int = 0                  # characters of text (no spaces)
    image_area: float = 0.0         # share of the page covered by images
    ocr: bool = False
    flag: str = ""                  # "no text layer", "little text", "garbled text"
    folio: str = ""


@dataclass
class Interrupt:
    start: int
    end: int
    display: str                    # "Deu-‖143‖teronomy"
    joined: str                     # "Deuteronomy"


class PdfBook:
    """The text of a PDF, as paragraphs and notes ready for the Scripture and term scanners."""

    def __init__(self, path: str | Path, known_word=None, progress=None):
        """known_word(word) -> bool: is this a book name or a term (for rejoining hyphenated words)?"""
        import pdfplumber
        self.path = Path(path)
        self.known_word = known_word or (lambda w: False)
        self.progress = progress or (lambda done, total: None)
        self.pages: list[PageInfo] = []
        self.lines: list[list[Line]] = []
        self.warnings: list[str] = []
        self.body_segments: list[Segment] = []
        self.note_segments: dict = {}          # (page, number) -> [Segment]
        self.note_ordinals: dict = {}
        self.ocr = False
        self.body_size = 10.0
        self.pitch = 12.0
        self.font_name = ""
        self._fonts = Counter()
        self._rules = {}
        self.skipped_index = ""
        self._page_heights = []
        with pdfplumber.open(str(self.path)) as pdf:
            self._labels = self._pdf_page_labels()
            n = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                self.progress(i, n)
                info, lines = self._read_page(i, page)
                self.pages.append(info)
                self.lines.append(lines)
            self.progress(n, n)
        if not self.pages:
            raise RuntimeError("The PDF has no pages.")
        self._body_size()
        self._margins()
        self._notes_and_headings()
        self._labels_and_flags()
        self._assemble()

    # -- reading ---------------------------------------------------------------
    def _pdf_page_labels(self) -> list[str] | None:
        try:
            from pypdf import PdfReader
            r = PdfReader(str(self.path))
            if "/PageLabels" not in r.trailer["/Root"]:
                return None
            return list(r.page_labels)
        except Exception:
            return None

    def _read_page(self, i, page):
        info = PageInfo(i)
        W, H = float(page.width), float(page.height)
        self._page_heights.append(H)
        area = 0.0
        for im in page.images:
            try:
                w = max(0.0, min(float(im["x1"]), W) - max(float(im["x0"]), 0.0))
                h = max(0.0, min(float(im["bottom"]), H) - max(float(im["top"]), 0.0))
                area += w * h
            except Exception:
                pass
        info.image_area = min(1.0, area / (W * H)) if W and H else 0.0
        chars = []
        fonts = Counter()
        keep = _trim_area(page, H)
        for c in page.chars:
            if not c.get("upright", True):
                continue
            if keep is not None:              # printer's marks and the slug line lie outside the trim
                cx, cy = (float(c["x0"]) + float(c["x1"])) / 2, (float(c["top"]) + float(c["bottom"])) / 2
                if not (keep[0] <= cx <= keep[2] and keep[1] <= cy <= keep[3]):
                    continue
            t = c.get("text") or ""
            if not t:
                continue
            fn = c.get("fontname") or ""
            ital = bool(re.search(r"italic|oblique|[-,]it\b|[a-z]it$", fn, re.I))
            chars.append(Char(t, float(c["x0"]), float(c["x1"]), float(c["top"]), float(c["bottom"]),
                              float(c.get("size") or 0.0), ital))
            if t.strip():
                fonts[fn] += 1
        info.chars = sum(1 for c in chars if c.text.strip())
        info.ocr = info.chars > 0 and info.image_area > 0.7
        self._fonts.update(fonts)
        rules = []
        for ln in list(page.lines) + list(page.rects):
            try:
                if abs(float(ln["bottom"]) - float(ln["top"])) < 2.0 and float(ln["x1"]) - float(ln["x0"]) > 20:
                    rules.append((float(ln["top"]), float(ln["x0"]), float(ln["x1"])))
            except Exception:
                pass
        self._rules[i] = rules
        return info, self._lines_of(i, chars, W, H)

    def _lines_of(self, pno, chars, W, H) -> list[Line]:
        if not chars:
            return []
        chars.sort(key=lambda c: (c.bottom, c.x0))
        groups: list[list[Char]] = []
        for c in chars:
            sz = c.size or 10.0
            if groups:
                g = groups[-1]
                base = max(x.bottom for x in g)
                if abs(c.bottom - base) <= 0.25 * sz:
                    g.append(c)
                    continue
            groups.append([c])
        # superscripts form little groups of their own: put them into the line they rise from
        sizes = [statistics.median([c.size for c in g if c.text.strip()] or [10.0]) for g in groups]
        merged: list[list[Char]] = []
        for k, g in enumerate(groups):
            small = sizes[k]
            nxt = k + 1 < len(groups)
            if nxt and small < 0.85 * sizes[k + 1]:
                ng = groups[k + 1]
                top = min(x.top for x in ng)
                bot = max(x.bottom for x in ng)
                if all(c.bottom > top and c.bottom < bot for c in g):
                    groups[k + 1] = g + ng
                    continue
            merged.append(g)
        # a page set in two columns: split each line at the gutter, so the columns are read one
        # after the other (lines that cross the gutter, such as full-width notes, stay whole)
        gx = _gutter(merged, W)
        cols = [0] * len(merged)
        if gx is not None:
            whole = _keep_whole(merged, gx)
            split, cols = [], []
            for g, keep in zip(merged, whole):
                if keep:
                    split.append(g)
                    cols.append(0)
                    continue
                for side, part in ((1, [c for c in g if c.x1 <= gx]), (2, [c for c in g if c.x1 > gx])):
                    if part:
                        split.append(part)
                        cols.append(side)
            merged = split
        lines = []
        for g, col in zip(merged, cols):
            if not any(c.text.strip() for c in g):
                continue
            g.sort(key=lambda c: c.x0)
            size = statistics.median([c.size for c in g if c.text.strip()])
            base = statistics.median([c.bottom for c in g if c.text.strip() and c.size >= 0.85 * size] or
                                     [max(c.bottom for c in g)])
            ln = Line(pno, min(c.top for c in g), max(c.bottom for c in g), g[0].x0, g[-1].x1, size, col=col)
            seq: list[Char] = []                  # visual order, with spaces put in where there are gaps
            sups = []
            lead_sup = ""
            prev = None
            sup_run = ""
            for c in g:
                is_sup = (c.size < 0.8 * size and c.text.isdigit() and base - c.bottom > 0.15 * size)
                if is_sup:
                    sup_run += c.text
                    prev = c
                    continue
                if sup_run:
                    if not seq:
                        lead_sup = sup_run
                    else:
                        sups.append((sum(len(x.text) for x in seq), sup_run))
                    sup_run = ""
                hebrew_pair = prev is not None and (HEB_LETTER.match(prev.text) or HEB_MARK.match(prev.text)) and \
                    (HEB_LETTER.match(c.text) or HEB_MARK.match(c.text))
                if prev is not None and not hebrew_pair and c.text != " " and (not seq or seq[-1].text != " "):
                    gap = c.x0 - prev.x1
                    if gap > 0.22 * (c.size or size) and prev.text != " ":
                        seq.append(Char(" ", prev.x1, c.x0, c.top, c.bottom, c.size, False))
                seq.append(c)
                prev = c
            if sup_run:
                if not seq:
                    lead_sup = sup_run
                else:
                    sups.append((sum(len(x.text) for x in seq), sup_run))
            ln.lead_sup = lead_sup
            out, ital = [], []
            for c in _rtl_fix(seq):
                for ch in c.text:
                    out.append(ch)
                    ital.append(c.italic)
            text = "".join(out)
            # trim spaces, keeping the italic flags and superscript offsets aligned
            lead = len(text) - len(text.lstrip(" "))
            text2 = text.strip(" ")
            ln.text = text2
            ln.italic = ital[lead:lead + len(text2)]
            ln.sups = [(max(0, min(len(text2), o - lead)), d) for o, d in sups]
            if ln.lead_sup and not text2:
                ln.text = ""
            lines.append(ln)
        lines.sort(key=lambda l: l.top)
        return _column_order(lines) if gx is not None else lines

    # -- the book's norms --------------------------------------------------------
    def _body_size(self):
        cnt = Counter()
        for lines in self.lines:
            for ln in lines:
                cnt[round(ln.size * 2) / 2] += len(ln.text)
        if cnt:
            self.body_size = cnt.most_common(1)[0][0]
        if self._fonts:
            self.font_name = font_family(self._fonts.most_common(1)[0][0])
        gaps = []
        for ls in self.lines:
            body = [l for l in ls if abs(l.size - self.body_size) < 0.6]
            gaps.extend(b.top - a.top for a, b in zip(body, body[1:]) if 0 < b.top - a.top < 3 * self.body_size)
        if gaps:
            self.pitch = statistics.median(gaps)

    def _margins(self):
        """Running heads and folios: lines in the top or bottom margin, on many pages."""
        text_pages = [i for i, ls in enumerate(self.lines) if ls]
        self._head_y = self._foot_y = None
        if not text_pages:
            return
        tops, bots = [], []
        for i in text_pages:
            ls = self.lines[i]
            # a running head or foot stands apart from the text: an extra gap, or a different size
            if len(ls) > 1 and self._apart(ls[0], ls[1]):
                tops.append(round(ls[0].top))
            if len(ls) > 1 and self._apart(ls[-2], ls[-1]):
                bots.append(round(ls[-1].bottom))
        self._head_y = self._band(tops, len(text_pages))
        self._foot_y = self._band(bots, len(text_pages))

    def _apart(self, a: Line, b: Line) -> bool:
        return (b.top - a.top) > 1.3 * self.pitch or abs(a.size - b.size) > 0.5 or \
            bool(FOLIO_RE.match(a.text) or FOLIO_RE.match(b.text))

    @staticmethod
    def _band(values, n):
        if not values:
            return None
        c = Counter()
        for v in values:
            c[v] += 1
            c[v - 1] += 0.5
            c[v + 1] += 0.5
        y, k = c.most_common(1)[0]
        return y if k >= max(3, 0.3 * n) else None

    def _notes_and_headings(self):
        bs = self.body_size
        for i, ls in enumerate(self.lines):
            if not ls:
                continue
            # running heads and folios
            H = self._page_heights[i]
            if len(ls) > 1 and self._apart(ls[0], ls[1]) and (
                    (self._head_y is not None and abs(ls[0].top - self._head_y) <= 3) or
                    (ls[0].bottom < 0.1 * H and ls[0].size < bs * 0.95)):
                ls[0].kind = "head"
            if len(ls) > 1 and self._apart(ls[-2], ls[-1]) and (
                    (self._foot_y is not None and abs(ls[-1].bottom - self._foot_y) <= 3) or
                    (ls[-1].top > 0.9 * H and ls[-1].size < bs * 0.95)):
                ls[-1].kind = "foot"
            rest = [l for l in ls if l.kind == "body"]
            # a folio may also sit alone in the top or bottom margin
            for ln in (rest[:1] + rest[-1:]):
                if FOLIO_RE.match(ln.text) and (ln is rest[0] or ln is rest[-1]):
                    if ln.top < 0.12 * self._page_h(i) or ln.bottom > 0.85 * self._page_h(i):
                        ln.kind = "foot" if ln.bottom > 0.5 * self._page_h(i) else "head"
            rest = [l for l in ls if l.kind == "body"]
            # footnotes: a block of smaller type at the foot of the page
            k = len(rest)
            while k > 0 and rest[k - 1].size <= bs * 0.92 and rest[k - 1].size > bs * 0.5:
                k -= 1
            block = rest[k:]
            first_numbered = bool(block) and bool(block[0].lead_sup or NOTE_NUM_RE.match(block[0].text))
            if block and k > 0 and any(abs(l.size - bs) < 0.6 and len(l.text) > 20 for l in rest[:k]):
                above = rest[k - 1]
                has_rule = any(above.bottom - 2 <= y <= block[0].top + 2 for y, _, _ in self._rules.get(i, []))
                prev_notes = [l for l in self.lines[i - 1] if l.kind == "note"] if i > 0 else []
                same_look = bool(prev_notes) and abs(prev_notes[-1].size - block[0].size) < 0.3 and \
                    abs(min(l.x0 for l in prev_notes) - min(l.x0 for l in block)) < bs
                numbered = sum(1 for b in block if b.lead_sup or NOTE_NUM_RE.match(b.text))
                # a footnote block starts with a note number; or it carries on a note from the page
                # before (same size and margin) and goes on to numbered notes or sits under a rule
                if first_numbered or (same_look and (numbered or has_rule)):
                    for b in block:
                        b.kind = "note"
            elif block and k == 0 and first_numbered and len(block) >= 1:
                for b in block:                           # a page of notes only: endnotes
                    b.kind = "note"
                    b.endnote = True
            body_left = _mode([round(l.x0) for l in rest[:k]]) if k else 0
            body_right = _mode([round(l.x1) for l in rest[:k]]) if k else 0
            for j, ln in enumerate(rest[:k]):
                gap_above = ln.top - rest[j - 1].top if j else 99
                gap_below = rest[j + 1].top - ln.top if j + 1 < k else 99
                apart = gap_above > 1.3 * self.pitch and gap_below > 1.2 * self.pitch
                short = len(ln.text) < 70
                caps = sum(c.isupper() for c in ln.text) > 0.8 * max(1, sum(c.isalpha() for c in ln.text))
                centred = ln.x0 > body_left + 2 * bs and abs((ln.x0 - body_left) - (body_right - ln.x1)) < bs
                if ln.size >= bs * 1.15 or (short and apart and (caps or centred) and
                                            not NOTE_NUM_RE.match(ln.text)):
                    ln.kind = "heading"

    def _page_h(self, i):
        return self._page_heights[i]

    def _labels_and_flags(self):
        # folio candidates: a number at either end of a running head or foot (feet first)
        cands: dict = {}
        for i, ls in enumerate(self.lines):
            out = []
            for ln in sorted((l for l in ls if l.kind in ("head", "foot")), key=lambda l: l.kind != "foot"):
                toks = ln.text.split()
                for t in (toks[-1:] + toks[:1]) if len(toks) > 1 else toks:
                    if FOLIO_RE.match(t) and t not in out:
                        out.append(t)
            cands[i] = out
        # arabic folios run on with the PDF pages: the most common offset wins, and a number that
        # doesn't fit it (a chapter number in a running head) is not taken as the page number
        offs, romans = Counter(), Counter()
        for i, cs in cands.items():
            for t in cs:
                if t.isdigit():
                    offs[int(t) - i] += 1
                elif roman_to_int(t):
                    romans[roman_to_int(t) - i] += 1
        off0 = offs.most_common(1)[0][0] if offs else None
        roff0 = romans.most_common(1)[0][0] if romans else None
        for i, cs in cands.items():
            for t in cs:
                if (t.isdigit() and int(t) - i == off0) or \
                        (not t.isdigit() and roman_to_int(t) and roman_to_int(t) - i == roff0):
                    self.pages[i].folio = t
                    break
            else:
                # a new numbering (another part of the book): taken if a neighbouring page agrees
                for t in cs:
                    if t.isdigit() and any(str(int(t) + d) in cands.get(i + d, []) for d in (-1, 1)):
                        self.pages[i].folio = t
                        break
        # arabic folios: one offset for the book (pages without a folio are filled in from it)
        offs = Counter()
        romans = Counter()
        for p in self.pages:
            if p.folio.isdigit():
                offs[int(p.folio) - p.index] += 1
            elif p.folio and roman_to_int(p.folio):
                romans[roman_to_int(p.folio) - p.index] += 1
        off = offs.most_common(1)[0][0] if offs else None
        roff = romans.most_common(1)[0][0] if romans else None
        first_arabic = min((p.index for p in self.pages if p.folio.isdigit() and int(p.folio) - p.index == off),
                           default=None)
        for p in self.pages:
            if p.folio:
                p.label, p.label_source = p.folio, "folio"
            elif self._labels and p.index < len(self._labels) and self._labels[p.index]:
                p.label, p.label_source = self._labels[p.index], "pdf"
            elif off is not None and first_arabic is not None and p.index >= first_arabic and p.index + off >= 1:
                p.label, p.label_source = str(p.index + off), "inferred"
            elif roff is not None and p.index + roff >= 1 and (first_arabic is None or p.index < first_arabic):
                p.label, p.label_source = _int_to_roman(p.index + roff), "inferred"
            else:
                p.label, p.label_source = str(p.index + 1), "index"
        # OCR and text quality
        text_pages = [p for p in self.pages if p.chars]
        self.ocr = bool(text_pages) and sum(1 for p in text_pages if p.ocr) >= 0.5 * len(text_pages)
        counts = [p.chars for p in self.pages if p.chars >= 50]
        med = statistics.median(counts) if counts else 0
        for p, ls in zip(self.pages, self.lines):
            text = " ".join(l.text for l in ls)
            if p.chars == 0:
                if p.image_area > 0.5:
                    p.flag = "no text layer: a scanned page that wasn't OCR'd?"
                continue
            bad = len(re.findall("\\(cid:\\d+\\)|[\ufffd\ue000-\uf8ff\x00-\x08\x0e-\x1f]", text))
            words = re.findall(r"\S+", text)
            odd = sum(1 for wd in words if GARBLE_RE.search(wd) or
                      sum(1 for ch in wd if unicodedata.category(ch) in ("So", "Sm", "Co", "Cn")) >= 3)
            if bad > 0.05 * max(1, p.chars) or (len(words) > 20 and odd > 0.3 * len(words)):
                p.flag = "garbled text: the text layer may not match the printed page"
            elif med and p.chars < 0.25 * med and (p.ocr or p.image_area > 0.3):
                p.flag = "little text compared with the rest of the book: check the OCR of this page"

    # -- paragraphs and notes ----------------------------------------------------------
    def _assemble(self):
        segs: list[Segment] = []
        cur: Segment | None = None
        prev: Line | None = None
        prev_page_full = False
        note_cur = None                     # (page, number) of the note being read
        last_note_key = None
        idx = 0
        nidx = 0
        for i, ls in enumerate(self.lines):
            body = [l for l in ls if l.kind in ("body", "heading")]
            # the text's left and right edges: one pair per column on a page in two columns
            edges = {}
            for c in {l.col for l in body}:
                xs = [l for l in body if l.kind == "body" and l.col == c]
                if xs:
                    edges[c] = (_mode([round(l.x0) for l in xs]), _mode([round(l.x1) for l in xs]))
            whole = edges.get(0) or next(iter(edges.values()), (0, 0))

            def left(ln):
                return edges.get(ln.col, whole)[0]

            def right(ln):
                return edges.get(ln.col, whole)[1]

            def runs_on(ln):
                """The paragraph runs on past this line (to the next column or page): the line is
                full, or stops mid-sentence."""
                return ln.kind == "body" and (
                    ln.text[-1:] in HYPHENS or ln.text[-1:] not in ".?!”\"’)" or
                    (ln.x1 >= right(ln) - 2 * self.body_size and ln.text[-1:] not in ".?!”\""))
            for j, ln in enumerate(body):
                if not ln.text:
                    continue
                new_par = False
                if cur is None or ln.kind == "heading" or (prev is not None and prev.kind == "heading"):
                    new_par = True
                elif prev is not None and prev.page == ln.page and prev.col == 1 and ln.col == 2 \
                        and ln.top < prev.top:
                    # from the foot of the left column to the head of the right
                    if ln.x0 > left(ln) + 0.8 * self.body_size or not runs_on(prev):
                        new_par = True
                elif prev is not None and prev.page == ln.page:
                    pitch = ln.top - prev.top
                    if ln.x0 > prev.x0 + 0.8 * self.body_size:      # an indented first line, or a block quote
                        new_par = True
                    elif abs(ln.size - prev.size) > 0.3:
                        new_par = True
                    elif pitch > 1.6 * self.pitch:
                        new_par = True
                    elif prev.x1 < right(prev) - 2 * self.body_size and prev.text[-1:] in SENT_END:
                        new_par = True
                else:                                     # first line on a new page
                    if ln.x0 > left(ln) + 0.8 * self.body_size or not prev_page_full:
                        new_par = True
                if new_par:
                    cur = Segment("pdf", idx)
                    idx += 1
                    cur.pages = []
                    cur.interrupts = []
                    cur.heading = ln.kind == "heading"
                    cur.level = 0 if cur.heading else None
                    cur.anchor_list = []
                    segs.append(cur)
                    _append(cur, ln, None, self, i)
                else:
                    _append(cur, ln, prev, self, i)
                prev = ln
            if body:
                # the paragraph runs on to the next page: the last line is full, or stops mid-sentence
                prev_page_full = runs_on(body[-1])
            # notes on this page
            notes = [l for l in ls if l.kind == "note" and l.text]
            nleft = min((round(l.x0) for l in notes), default=0)
            for ln in notes:
                m = NOTE_NUM_RE.match(ln.text)
                num = ln.lead_sup
                if not num and m and ln.x0 <= nleft + 2 * self.body_size:
                    # a plain number starts a note only if it follows on from the last note's number
                    want = _numval(note_cur.note_number) + 1 if note_cur is not None else None
                    if want is None or _numval(m.group(1)) in (want, 1):
                        num = m.group(1)
                cut = 0
                if not ln.lead_sup and num:
                    cut = m.end()
                if num:
                    key = (i, num)
                    seg = Segment("pdfnote", nidx)
                    nidx += 1
                    seg.pages, seg.interrupts = [], []
                    seg.note_kind, seg.note_id = ("endnote" if ln.endnote else "footnote"), f"{i}:{num}"
                    seg.note_number = num
                    seg.anchor_list = []
                    self.note_segments[key] = [seg]
                    self.note_ordinals[key] = len(self.note_ordinals) + 1
                    note_cur = seg
                    last_note_key = key
                    sub = _trimmed(ln, cut)
                    _append(seg, sub, None, self, i)
                elif note_cur is not None:
                    # a note running on from the previous page, or the next line of this one
                    if note_cur.pages and note_cur.pages[-1] != i and last_note_key is not None:
                        cont = Segment("pdfnote", nidx)
                        nidx += 1
                        cont.pages, cont.interrupts = [], []
                        cont.note_kind = "footnote"
                        cont.note_id = f"{i}:{note_cur.note_number}+"
                        cont.note_number = note_cur.note_number
                        cont.anchor_list = []
                        self.note_segments[last_note_key].append(cont)
                        note_cur = cont
                        _append(cont, ln, None, self, i)
                    else:
                        _append(note_cur, ln, note_cur._last_line, self, i)
            # superscript anchors in this page's body lines -> the note with that number
        # the bibliography is marked as in Word documents; a printed index (the book's own) is left out
        from .docx_io import mark_bibliography
        mark_bibliography(segs)
        keep, inside = [], False
        for seg in segs:
            if seg.heading:
                inside = bool(INDEX_HEADING_RE.match(seg.text))
                if inside:
                    self.skipped_index = self.label(seg.pages[0]) if seg.pages else ""
            if not inside:
                keep.append(seg)
        segs = keep
        self.body_segments = segs
        # anchors: the body superscript numbers (offsets in their paragraph) -> note keys
        for seg in segs:
            seg.anchors = []
            for off, digits, page in seg.anchor_list:
                key = None
                for p in (page, page + 1, page - 1):
                    if (p, digits) in self.note_segments:
                        key = (p, digits)
                        break
                if key is not None:
                    seg.anchors.append(_Anchor("footnote", key, off))

    # -- helpers for the review ---------------------------------------------------------
    def page_of(self, seg: Segment, offset: int) -> int:
        if not seg.pages:
            return 0
        return seg.pages[min(max(offset, 0), len(seg.pages) - 1)]

    def label(self, page: int) -> str:
        return self.pages[page].label if 0 <= page < len(self.pages) else str(page + 1)

    def snippet(self, seg: Segment, s: int, e: int, before: int = 70, after: int = 50) -> str:
        """Context with the reference between ⟦ ⟧ and page breaks shown as ‖143‖."""
        a = max(0, s - before)
        b = min(len(seg.text), e + after)
        out = ["…" if a > 0 else ""]
        for k in range(a, b):
            if k == s:
                out.append("⟦")
            if k > a and seg.pages[k] != seg.pages[k - 1]:
                out.append(f"‖{self.label(seg.pages[k])}‖")
            out.append(seg.text[k])
            if k == e - 1:
                out.append("⟧")
        if b < len(seg.text):
            out.append("…")
        return "".join(out).replace("\t", " ").replace("\n", " ")

    def flagged_pages(self) -> list[PageInfo]:
        return [p for p in self.pages if p.flag]


@dataclass
class _Anchor:
    kind: str
    note_id: tuple
    offset: int


INDEX_HEADING_RE = re.compile(r"^\s*(?:(?:scripture|subject|author|name|general|topical|ancient sources?|biblical)"
                              r"\s+)?index(?:es)?(?:\s+of\s+.+)?\s*$|^\s*indexes\s*$", re.I)
FOLIO_RE = re.compile(r"^(?:\d{1,4}|[ivxlcdm]{1,8}|[IVXLCDM]{1,8})$")
NOTE_NUM_RE = re.compile(r"^(\d{1,3}|[ivxlc]{1,6})[.)]?\s+(?=\S)")
GARBLE_RE = re.compile(r"[a-z]\d[a-z]")


def _trim_area(page, H: float):
    """(x0, top, x1, bottom) of the page's trim box (or, failing that, its bleed box) when the PDF
    has printer's marks around the page; None when the whole page is the page."""
    try:
        from pdfminer.pdftypes import resolve1
        attrs = page.page_obj.attrs
        media = [float(v) for v in resolve1(attrs.get("MediaBox"))]
        for key in ("TrimBox", "BleedBox"):
            box = resolve1(attrs.get(key))
            if not box:
                continue
            x0, y0, x1, y1 = (float(v) for v in box)
            if (x1 - x0) < (media[2] - media[0]) - 2 or (y1 - y0) < (media[3] - media[1]) - 2:
                ox, oy = media[0], media[1]
                return (x0 - ox, H - (y1 - oy), x1 - ox, H - (y0 - oy))
            return None
    except Exception:
        pass
    return None


def _gutter(groups: list[list[Char]], W: float) -> float | None:
    """The x of the gap between two columns of text, or None when the page isn't set in two
    columns.  The gap is a strip in the middle of the page that most lines don't cross, with text
    on both sides of it on many lines."""
    lo, hi = int(W * 0.3), int(W * 0.7)
    if hi - lo < 10:
        return None
    rows = []
    for g in groups:
        iv = sorted((c.x0, c.x1) for c in g if c.text.strip())
        if iv:
            rows.append(iv)
    if len(rows) < 8:
        return None
    count = [0] * (hi - lo + 1)
    for iv in rows:
        hit = set()
        for a, b in iv:
            for x in range(max(lo, int(a)), min(hi, int(b) + 1) + 1):
                hit.add(x)
        for x in hit:
            count[x - lo] += 1
    least = min(count)
    if least > 0.4 * len(rows):
        return None
    # the widest run of x at the least count; its middle
    best, run_start = (0, None), None
    for k, n in enumerate(count + [least + 1]):
        if n == least and run_start is None:
            run_start = k
        elif n != least and run_start is not None:
            if k - run_start > best[0]:
                best = (k - run_start, run_start)
            run_start = None
    gx = lo + best[1] + best[0] / 2
    both = 0
    for iv in rows:
        left = [b for a, b in iv if b < gx]
        right = [a for a, b in iv if a > gx]
        if left and right and min(right) - max(left) >= 8:
            both += 1
    return gx if both >= 6 else None


def _keep_whole(groups: list[list[Char]], gx: float) -> list[bool]:
    """Which lines of a two-column page are not split at the gutter: those that cross it, and the
    smaller type below the columns (footnotes, whose justified lines may happen to leave a gap there)."""
    info = []
    for g in groups:
        txt = [c for c in g if c.text.strip()]
        crosses = any(c.x0 - 0.5 <= gx <= c.x1 + 0.5 for c in txt)
        size = statistics.median([c.size for c in txt]) if txt else 0.0
        info.append((crosses, size, min((c.top for c in txt), default=0.0), max((c.bottom for c in txt), default=0.0)))
    col_sizes = [sz for cr, sz, _, _ in info if not cr and sz]
    if not col_sizes:
        return [True] * len(groups)
    col = statistics.median(col_sizes)
    last = max((bot for cr, sz, _, bot in info if not cr and sz >= 0.92 * col), default=0.0)
    return [cr or (sz < 0.92 * col and top >= last - 1) for cr, sz, top, _ in info]


def _column_order(lines: list[Line]) -> list[Line]:
    """Lines (sorted top to bottom) of a page in two columns, in reading order: between lines that
    run across the page, the left column, then the right.  A short line alone in the top or bottom
    margin (a running head or folio) is not part of a column."""
    def gap(a, b):
        return b.top - a.bottom
    n = len(lines)
    for k in range(n):                                  # from the top
        ln = lines[k]
        if ln.col == 0:
            continue
        if k + 1 < n and gap(ln, lines[k + 1]) > 0.8 * ln.size:
            ln.col = 0
            continue
        break
    for k in range(n - 1, -1, -1):                      # from the bottom
        ln = lines[k]
        if ln.col == 0:
            continue
        if k > 0 and gap(lines[k - 1], ln) > 0.8 * ln.size:
            ln.col = 0
            continue
        break
    out, block = [], []

    def flush():
        out.extend(sorted((l for l in block if l.col == 1), key=lambda l: l.top))
        out.extend(sorted((l for l in block if l.col == 2), key=lambda l: l.top))
        block.clear()
    for ln in lines:
        if ln.col == 0:
            flush()
            out.append(ln)
        else:
            block.append(ln)
    flush()
    return out


def _numval(s: str) -> int:
    """A note number's value: "12" -> 12, "iv" -> 4."""
    if s.isdigit():
        return int(s)
    return roman_to_int(s) or 0


def _mode(vals):
    if not vals:
        return 0
    return Counter(vals).most_common(1)[0][0]


def font_family(fontname: str) -> str:
    """"BCDEEE+EBGaramond-Regular" -> "EB Garamond"; "TimesNewRomanPSMT" -> "Times New Roman"."""
    n = re.sub(r"^[A-Z]{6}\+", "", fontname or "")
    n = re.split(r"[-,]", n)[0]
    n = re.sub(r"(?:PSMT|PS|MT|Std|Pro|LT)$", "", n)
    n = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", n)
    return n.strip()


def _rtl_fix(chars: list[Char]) -> list[Char]:
    """Hebrew is stored in visual order: put each Hebrew run back in reading order, keeping each
    letter's points with it."""
    out: list[Char] = []
    k = 0
    n = len(chars)
    while k < n:
        c = chars[k]
        if HEB_LETTER.match(c.text) or HEB_MARK.match(c.text):
            j = k
            while j < n and (HEB_LETTER.match(chars[j].text) or HEB_MARK.match(chars[j].text) or
                             chars[j].text in " ־" and j + 1 < n and
                             (HEB_LETTER.match(chars[j + 1].text) or HEB_MARK.match(chars[j + 1].text))):
                j += 1
            run = chars[k:j]
            clusters: list[list[Char]] = []
            marks = [x for x in run if HEB_MARK.match(x.text)]
            bases = [x for x in run if not HEB_MARK.match(x.text)]
            for b in bases:
                clusters.append([b])
            for m in marks:
                cx = (m.x0 + m.x1) / 2
                best = None
                for cl in clusters:
                    b = cl[0]
                    if b.text == " ":
                        continue
                    d = 0 if b.x0 - 0.5 <= cx <= b.x1 + 0.5 else min(abs(cx - b.x0), abs(cx - b.x1))
                    if best is None or d < best[0]:
                        best = (d, cl)
                if best is not None:
                    best[1].append(m)
            clusters.sort(key=lambda cl: -cl[0].x0)
            for cl in clusters:
                out.extend(cl)
            k = j
        else:
            out.append(c)
            k += 1
    return out


def _trimmed(ln: Line, cut: int) -> Line:
    if not cut:
        return ln
    t = Line(ln.page, ln.top, ln.bottom, ln.x0, ln.x1, ln.size, ln.text[cut:], ln.italic[cut:],
             [(o - cut, d) for o, d in ln.sups if o >= cut], ln.kind)
    return t


def _append(seg: Segment, ln: Line, prev: Line | None, book: PdfBook, page: int) -> None:
    """Add a line to a paragraph or note, joining hyphenated words where that is safe."""
    text, ital = ln.text, list(ln.italic)
    sups = list(ln.sups)
    if seg.text:
        last = seg.text.rstrip()
        m = re.search(r"([^\W\d_]+)[" + HYPHENS + r"]$", last)
        n = re.match(r"([^\W\d_]+)", text)
        joined = False
        if m and n and text[:1].islower():
            whole = m.group(1) + n.group(1)
            cross = seg.pages and seg.pages[-1] != page
            if cross:
                # across a page break: joined for reading, flagged in the review
                cut = len(seg.text) - len(last) + 1
                start = len(last) - len(m.group(0))
                disp = f"{m.group(1)}-‖{book.label(page)}‖{n.group(1)}"
                _drop_tail(seg, cut)
                seg.interrupts.append(Interrupt(start, start + len(whole), disp, whole))
                joined = True
            elif book.known_word(whole) or book.known_word(whole + "."):
                _drop_tail(seg, len(seg.text) - len(last) + 1)
                joined = True
            elif seg.text.endswith("­"):
                _drop_tail(seg, 1)
                joined = True
            elif seg.text[-1:] in HYPHENS and last == seg.text:
                joined = True                     # keep the hyphen ("well-known"), no space
        if not joined:
            seg.add(" ", False)
            seg.pages.append(page)
    base = len(seg.text)
    if seg.part == "pdf":
        for o, d in sups:
            seg.anchor_list.append((base + o, d, page))
    seg.text += text
    seg.italic.extend(ital)
    seg.langs.extend([None] * len(text))
    seg.pages.extend([page] * len(text))
    seg._last_line = ln


def _drop_tail(seg: Segment, n: int) -> None:
    if n <= 0:
        return
    seg.text = seg.text[:-n]
    del seg.italic[-n:]
    del seg.langs[-n:]
    del seg.pages[-n:]


# ---------------------------------------------------------------------------
# OCR tolerance: "Gen. l:l", "John 3;16"
# ---------------------------------------------------------------------------
OCR_TOKEN = re.compile(r"(?<![A-Za-z\d])([\dlI|]{1,3})([:;])([\dlI|]{1,3})(?![A-Za-z\d])")


def ocr_fix(text: str) -> tuple[str, list[int]]:
    """Read l, I and | as 1 and ; as : inside chapter:verse numbers.  Returns the text and
    the positions changed."""
    out = list(text)
    changed = []
    for m in OCR_TOKEN.finditer(text):
        tok = m.group(0)
        if not any(ch.isdigit() for ch in tok):
            # "Gen. l:l": no digit at all, so only right after a book-like word
            if m.group(2) != ":" or not re.search(r"[A-Z][a-z]{1,12}\.?\s$", text[max(0, m.start() - 16):m.start()]):
                continue
        if m.group(2) == ";" and not (m.group(1).isdigit() or m.group(3).isdigit()):
            continue
        for k in range(m.start(), m.end()):
            ch = text[k]
            if ch in "lI|":
                out[k] = "1"
                changed.append(k)
            elif ch == ";":
                out[k] = ":"
                changed.append(k)
    return "".join(out), changed
