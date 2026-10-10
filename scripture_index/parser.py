"""Scripture reference finder with context resolution, driven by a language.

Statuses (how the book of each chapter:verse was determined):

    explicit       book named right before it            ("Prov. 5:15", "Joh 3,16")
    chain          continues a list whose head named it  ("Prov. 1:1; 10:1")
    inferred       book carried from earlier text        ("In Proverbs 5 ... (5:17)")
    inferred-weak  as above, but the book was named long ago or before a new chapter
    verse-only     "v. 23", "verses 9-16" (chapter taken from context)
    chapter-only   "Proverbs 5" (no verse)
    italic         inside italics -- usually a book title
    citation       volume:page in a bibliographic citation ("HALOT, 1:93")
    invalid        chapter/verse impossible for the book
    unresolved     chapter:verse with no book anywhere in context
    manual         added by hand in the review table

Only explicit / chain / inferred / inferred-weak / manual are indexed by default.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from .catalog import Catalog
from .lang import SP, Language

DASH = "[–—\\-‑]"
HLET = "א-ת"
HN = "[" + HLET + "]{1,3}(?:[״\"”][" + HLET + "])?[׳'’]?"

INDEXED_STATUSES = {"explicit", "chain", "inferred", "inferred-weak", "manual"}
STATUS_LABELS = {
    "explicit": "Book named",
    "chain": "Book named (list)",
    "inferred": "Book from context",
    "inferred-weak": "Book from context (distant)",
    "verse-only": "Verse only",
    "chapter-only": "Chapter only",
    "italic": "Italic (possible title)",
    "citation": "Volume:page citation",
    "invalid": "Impossible chapter/verse",
    "unresolved": "No book found",
    "manual": "Added by hand",
}

# ---------------------------------------------------------------------------
# Hebrew numerals
# ---------------------------------------------------------------------------
HVAL = {"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9, "י": 10,
        "כ": 20, "ך": 20, "ל": 30, "מ": 40, "ם": 40, "נ": 50, "ן": 50, "ס": 60, "ע": 70,
        "פ": 80, "ף": 80, "צ": 90, "ץ": 90, "ק": 100, "ר": 200, "ש": 300, "ת": 400}


def heb_to_int(s: str) -> int | None:
    t = re.sub("[׳״'\"’”]", "", s or "")
    if not t or len(t) > 4 or any(c not in HVAL for c in t):
        return None
    vals = [HVAL[c] for c in t]
    if t.endswith("טו") or t.endswith("טז"):
        head = vals[:-2]
        if any(a < b for a, b in zip(head, head[1:])) or (head and head[-1] < 10):
            return None
        return sum(vals)
    if any(a < b for a, b in zip(vals, vals[1:])):
        return None
    if "יה" in t or "יו" in t:          # 15 and 16 are written טו / טז
        return None
    if len(set(c for c in t if HVAL[c] < 10)) > 1 or sum(1 for c in t if 10 <= HVAL[c] < 100) > 1:
        return None
    return sum(vals)


def int_to_heb(n: int) -> str:
    out = ""
    for v, c in ((400, "ת"), (300, "ש"), (200, "ר"), (100, "ק")):
        while n >= v:
            out += c
            n -= v
    if n == 15:
        return out + "טו"
    if n == 16:
        return out + "טז"
    for v, c in ((90, "צ"), (80, "פ"), (70, "ע"), (60, "ס"), (50, "נ"), (40, "מ"), (30, "ל"),
                 (20, "כ"), (10, "י")):
        if n >= v:
            out += c
            n -= v
            break
    for v, c in ((9, "ט"), (8, "ח"), (7, "ז"), (6, "ו"), (5, "ה"), (4, "ד"), (3, "ג"), (2, "ב"),
                 (1, "א")):
        if n >= v:
            out += c
            n -= v
            break
    return out


SFX_ORDER = {"": 0, "a": 1, "b": 2, "c": 3, "d": 4, "f": 5, "s": 5, "ff": 6, "ss": 6}


def _norm_sfx(s: str | None) -> str:
    return (s or "").rstrip(".")


# ---------------------------------------------------------------------------
# Reference value object
# ---------------------------------------------------------------------------
@dataclass
class Ref:
    book: str
    c1: int
    v1: int = 0
    s1: str = ""
    c2: int = 0
    v2: int = 0
    s2: str = ""
    cat: Catalog | None = field(default=None, repr=False, compare=False)

    @property
    def book_name(self) -> str:
        return self.cat.name(self.book) if self.cat else self.book

    def _num(self, n: int) -> str:
        if self.cat and self.cat.numerals == "hebrew":
            return int_to_heb(n)
        return str(n)

    def _sfx(self, s: str) -> str:
        return s + "." if s in ("f", "ff", "s", "ss") else s

    def label(self) -> str:
        sep = self.cat.label_sep if self.cat else ":"
        single = self.cat.get(self.book).single_chapter if self.cat and self.book in self.cat.books else False
        n = self._num
        if self.v1 == 0:
            s = n(self.c1)
            if self.c2 and self.c2 != self.c1:
                s += f"–{n(self.c2)}"
            return s
        start = f"{n(self.v1)}{self._sfx(self.s1)}" if single else f"{n(self.c1)}{sep}{n(self.v1)}{self._sfx(self.s1)}"
        if not self.c2:
            return start
        if self.c2 == self.c1 or single:
            return f"{start}–{n(self.v2)}{self._sfx(self.s2)}"
        return f"{start}–{n(self.c2)}{sep}{n(self.v2)}{self._sfx(self.s2)}"

    def sort_key(self) -> str:
        def sx(s):
            return str(SFX_ORDER.get(s, 0))
        end = f"{self.c2:03d}{self.v2:03d}{sx(self.s2)}" if self.c2 else "0000000"
        return f"{self.c1:03d}{self.v1:03d}{sx(self.s1)}{end}"

    def book_key(self) -> str:
        return self.cat.book_key(self.book)

    def display(self) -> str:
        return f"{self.book_name} {self.label()}"

    def valid(self) -> bool:
        if not self.cat or self.book not in self.cat.books:
            return False
        bk = self.cat.get(self.book)
        for c, v in ((self.c1, self.v1), (self.c2, self.v2)):
            if c == 0:
                continue
            if c > bk.chapters or c < 1 or v > 176:
                return False
        if self.c2 and (self.c2, self.v2) < (self.c1, self.v1):
            return False
        return True


@dataclass
class Hit:
    start: int
    end: int
    ref: Ref | None
    status: str
    reason: str = ""
    raw: str = ""

    @property
    def indexed_by_default(self) -> bool:
        return self.status in INDEXED_STATUSES


@dataclass
class Context:
    book: str | None = None
    chapter: int | None = None
    book_seg: int = -10_000
    stale: bool = False

    def copy(self) -> "Context":
        return copy.copy(self)


# ---------------------------------------------------------------------------
# Patterns that depend on the language
# ---------------------------------------------------------------------------
class Patterns:
    def __init__(self, lang: Language):
        p = lang.p
        seps = "".join(re.escape(s) for s in p.get("cv_seps", [":"]))
        self.sep = "[" + seps + "]"
        sfx_alts = []
        for s, _ in sorted(p.get("suffixes", []), key=lambda x: -len(x[0])):
            sfx_alts.append(re.escape(s) + r"\.?")
        sfx_alts.append(r"[a-d](?![A-Za-z])")
        self.sfx = "(?:" + "|".join(sfx_alts) + ")"
        num = r"\d{1,3}"
        self.cv = re.compile(
            r"(?<![\w:.,/])(?P<c1>" + num + ")" + self.sep + "(?P<v1>" + num + ")(?P<s1>" + self.sfx + ")?"
            r"(?:" + SP + "?" + DASH + SP + "?(?P<x>" + num + ")(?:" + self.sep + "(?P<y>" + num +
            "))?(?P<s2>" + self.sfx + ")?)?"
            r"(?!\d)(?!" + self.sep + r"\d)(?!" + SP + r"?(?:[ap]\.m\.|[AaPp][Mm]\b))")
        self.hcv = re.compile(
            r"(?P<c1>" + HN + r")" + SP + r"*[,:]" + SP + r"*(?P<v1>" + HN + r")"
            r"(?:" + SP + "*" + DASH + SP + "*(?P<x>" + HN + r")(?:" + SP + r"*[,:]" + SP + r"*(?P<y>" + HN + r"))?)?"
            r"(?![" + HLET + r"])") if p.get("numerals") == "hebrew" else None
        vw = "|".join(re.escape(w) for w in sorted(p.get("verse_words", []), key=len, reverse=True))
        vnum = r"\d{1,3}(?:" + self.sfx + r")?(?:" + SP + "?" + DASH + SP + r"?\d{1,3}(?:" + self.sfx + r")?)?"
        ands = "|".join(re.escape(w) for w in p.get("and_words", [])) or "(?!)"
        self.vw = re.compile(
            r"(?<![\w])(?P<vword>" + (vw or "(?!)") + r")" + SP + r"?(?P<vlist>" + vnum +
            r"(?:(?:," + SP + r"?|,?" + SP + r"(?:" + ands + r")" + SP + r")" + vnum + r")*)(?!\d)")
        self.vnum = re.compile(r"(?P<v>\d{1,3})(?P<s>" + self.sfx + r")?(?:" + SP + "?" + DASH + SP +
                               r"?(?P<v2>\d{1,3})(?P<s2>" + self.sfx + r")?)?")
        self.after_ch = re.compile(r"\.?" + SP + r"+(?P<c>\d{1,3})(?:" + SP + "?" + DASH + SP +
                                   r"?(?P<c2>\d{1,3}))?(?!\d)(?!" + self.sep + r"\d)")
        self.xch = re.compile(r"\.?" + SP + r"+(?P<c>\d{1,3})" + SP + "?" + DASH + SP + r"?(?P<x>\d{1,3})" +
                              self.sep + r"(?P<y>\d{1,3})(?!\d)")
        self.cv_next = re.compile(r"\.?" + SP + r"*\d{1,3}" + self.sep + r"\d")
        self.hcv_next = re.compile(SP + r"*" + HN + SP + r"*[,:]" + SP + r"*" + HN) if self.hcv else None
        self.attached_gap = re.compile(r"^\.?" + SP + r"*$")
        cfs = "|".join(re.escape(w) for w in p.get("cf_words", [])) or "(?!)"
        self.chain_gap = re.compile(
            r"^" + SP + r"*(?:[;,]" + SP + r"*(?:(?:" + cfs + r")" + SP + r"*)?"
            r"|,?" + SP + r"*(?:" + ands + r"|or)" + SP + r"+)$")
        spaced = "|".join(re.escape(s) for s in p.get("verse_list_spaced", [])) or "(?!)"
        tight = "|".join(re.escape(s) for s in p.get("verse_list_tight", [])) or "(?!)"
        self.cont = re.compile(
            r"(?:(?:" + spaced + r")" + SP + r"?|,?" + SP + r"(?:" + ands + r")" + SP + r"|(?:" + tight +
            r"))(?P<v>\d{1,3})(?P<s>" + self.sfx + r")?(?:" + SP + "?" + DASH + SP +
            r"?(?P<v2>\d{1,3})(?P<s2>" + self.sfx + r")?)?(?!\d)(?!" + self.sep + r"\d)")
        self.cont_ok_after = re.compile(
            r"(?:" + SP + r"*(?:[)\];,.”\"’»]|$)|,?" + SP + r"(?:" + ands + r")" + SP + r"\d|"
            + r"(?:" + tight + r")\d)")
        intro = "|".join(re.escape(w) for w in p.get("intro", [])) or "(?!)"
        self.intro_before = re.compile(r"(?:" + intro + r")" + SP + r"+$")


CITATION_BEFORE = re.compile(
    r"(?:\b(?:vols?|nos?|pp?|col|cols|Bd|Bde|S|Sp|t|tome)\." + SP + r"*\d*,?" + SP + r"*$"
    r"|\d{4}\)?[,.]?" + SP + r"*$"
    r"|\)[,.]?" + SP + r"*$"
    r"|\b[A-Z]{2,}[A-Za-z]*[,.]?" + SP + r"*$"
    r"|\b(?:ed|éd|Hg|hg)\.,?" + SP + r"*$)")
TIME_AFTER = re.compile(SP + r"?(?:o['’]clock|Uhr\b|h\b)")


def _is_italic(italic: list, s: int, e: int, text: str = "") -> bool:
    if not italic or e <= s:
        return False
    span = italic[s:e]
    if not (span and all(span)):
        return False
    letters = [f for ch, f in zip(text, italic) if ch.isalpha()] if text else italic
    if letters and sum(letters) / len(letters) > 0.6:
        return False
    if text and re.search(r"[(\[;]" + SP + r"*(?:cf\.|vgl\." + SP + r"*)?$", text[max(0, s - 6):s]):
        return False
    return True


def _in_parens(text: str, pos: int) -> bool:
    depth = 0
    for ch in text[:pos]:
        if ch in "([":
            depth += 1
        elif ch in ")]" and depth:
            depth -= 1
    return depth > 0


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------
class Scanner:
    def __init__(self, lang: Language, distant_after: int = 15):
        self.lang = lang
        self.cat = lang.cat
        self.pt = Patterns(lang)
        self.ctx = Context()
        self.distant_after = distant_after
        self.master = re.compile(
            "(?P<book>" + lang.book_re.pattern + ")|(?P<cv>" + self.pt.cv.pattern + ")|(?P<vw>" +
            self.pt.vw.pattern + ")")

    def heading(self) -> None:
        self.ctx.stale = True

    def ref(self, book, c1, v1=0, s1="", c2=0, v2=0, s2=""):
        return Ref(book, c1, v1, _norm_sfx(s1), c2, v2, _norm_sfx(s2), self.cat)

    def mkref(self, book, c1, v1, s1, x, y, s2):
        if x is None:
            return self.ref(book, c1, v1, s1)
        x = int(x)
        if y is not None:
            y = int(y)
            return self.ref(book, c1, v1, s1, c1 if x == c1 else x, y, s2)
        return self.ref(book, c1, v1, s1, c1, x, s2)

    def scan_segment(self, text, italic, seg_no, anchors=None, ctx=None):
        use = ctx if ctx is not None else self.ctx
        return self._scan(text, italic, use, seg_no, sorted(anchors or []))

    # -------------------------------------------------------------------------
    def _set_book(self, ctx, book, seg_no):
        ctx.book, ctx.chapter, ctx.book_seg, ctx.stale = book, None, seg_no, False

    def _scan(self, text, italic, ctx, seg_no, anchors):
        pt = self.pt
        hits: list[Hit] = []
        snaps: dict = {}
        ai = 0

        def flush(upto):
            nonlocal ai
            while ai < len(anchors) and anchors[ai] <= upto:
                snaps[anchors[ai]] = ctx.copy()
                ai += 1

        last_book = None      # (book, end, italic, start)
        chain = None
        pos, n = 0, len(text)
        while pos < n:
            m = self.master.search(text, pos)
            if not m:
                break
            flush(m.start())
            if m.group("book") is not None:
                consumed = self._book(m, text, italic, ctx, seg_no, hits)
                if consumed is None:
                    pos = m.end()
                    continue
                pos, last_book, chain = consumed
                continue
            if m.group("cv") is not None:
                s, e = m.start("cv"), m.end("cv")
                if TIME_AFTER.match(text, e):
                    pos = e
                    continue
                c1, v1 = int(m.group("c1")), int(m.group("v1"))
                pos, last_book, chain = self._cv(text, italic, ctx, seg_no, hits, s, e, c1, v1,
                                                 m.group("s1"), m.group("x"), m.group("y"),
                                                 m.group("s2"), last_book, chain)
                continue
            if m.group("vw") is not None:
                s, e = m.start("vw"), m.end("vw")
                vlist = m.group("vlist")
                base = m.start("vlist")
                for im in pt.vnum.finditer(vlist):
                    is_, ie = base + im.start(), base + im.end()
                    if ctx.book is not None and ctx.chapter:
                        v2 = im.group("v2")
                        r = self.ref(ctx.book, ctx.chapter, int(im.group("v")), im.group("s") or "",
                                     ctx.chapter if v2 else 0, int(v2) if v2 else 0, im.group("s2") or "")
                        hits.append(Hit(is_, ie, r, "verse-only" if r.valid() else "invalid",
                                        raw=text[s:e], reason=f"chapter {ctx.chapter} assumed from context"))
                    else:
                        hits.append(Hit(is_, ie, None, "unresolved", raw=text[s:e],
                                        reason="verse number with no chapter in context"))
                chain = None
                last_book = None
                pos = e
                continue
            pos = m.end()
        flush(n + 1)
        return hits, snaps

    # -------------------------------------------------------------------------
    def _book(self, m, text, italic, ctx, seg_no, hits):
        pt, lang = self.pt, self.lang
        name_s, name_e = m.start("name"), m.end("name")
        info = lang.resolve(m.group("name"))
        if info is None:
            return None
        start, end = m.start("book"), m.end("book")
        followed = (pt.cv_next.match(text, end) or pt.after_ch.match(text, end) or
                    (pt.hcv_next.match(text, end) if pt.hcv_next else None))
        if not followed:
            # back off to a shorter spelling that *is* followed by a number
            for cm, cinfo in lang.candidates_at(text, name_s)[1:]:
                ce = cm.end()
                if (pt.cv_next.match(text, ce) or pt.after_ch.match(text, ce) or
                        (pt.hcv_next.match(text, ce) if pt.hcv_next else None)):
                    info, end, name_e = cinfo, ce, ce
                    break
        bid, kind, short, bare_ok = info
        bk = self.cat.get(bid)
        ital = _is_italic(italic, name_s, name_e, text)

        # Hebrew-numeral chapter,verse right after the book
        if pt.hcv is not None:
            hm = re.compile(SP + "*").match(text, end)
            hstart = hm.end()
            hm = pt.hcv.match(text, hstart)
            if hm:
                c1, v1 = heb_to_int(hm.group("c1")), heb_to_int(hm.group("v1"))
                x = heb_to_int(hm.group("x")) if hm.group("x") else None
                y = heb_to_int(hm.group("y")) if hm.group("y") else None
                if c1 and v1 and (hm.group("x") is None or x):
                    r = self.mkref(bid, c1, v1, "", x, y, "")
                    st = "italic" if ital else "explicit"
                    if not r.valid():
                        st = "invalid"
                    hits.append(Hit(start, hm.end(), r, st, raw=text[start:hm.end()]))
                    if st == "explicit":
                        self._set_book(ctx, bid, seg_no)
                        ctx.chapter = r.c2 if r.c2 and r.c2 != r.c1 else r.c1
                    return hm.end(), None, dict(book=bid, chapter=ctx.chapter, status=st, end=hm.end(), heb=True)

        if pt.cv_next.match(text, end):
            if not ital:
                self._set_book(ctx, bid, seg_no)
            return end, (bid, end, ital, start), None
        xm = pt.xch.match(text, end)
        if xm:
            r = self.ref(bid, int(xm.group("c")), 1, "", int(xm.group("x")), int(xm.group("y")), "")
            st = "italic" if ital else "explicit"
            if not r.valid():
                st = "invalid"
            hits.append(Hit(start, xm.end(), r, st, raw=text[start:xm.end()]))
            if st == "explicit":
                self._set_book(ctx, bid, seg_no)
                ctx.chapter = r.c2
            return xm.end(), None, dict(book=bid, chapter=r.c2, status=st, end=xm.end())
        cm = pt.after_ch.match(text, end)
        if cm and not short:
            c = int(cm.group("c"))
            c2 = int(cm.group("c2")) if cm.group("c2") else 0
            if bk.single_chapter:
                r = self.ref(bid, 1, c, "", 1 if c2 else 0, c2, "")
                st = "italic" if ital else "explicit"
                if not r.valid():
                    st = "invalid"
                hits.append(Hit(start, cm.end(), r, st, raw=text[start:cm.end()]))
                if not ital:
                    self._set_book(ctx, bid, seg_no)
                    ctx.chapter = 1
                return cm.end(), None, dict(book=bid, chapter=1, status="explicit" if not ital else "italic",
                                            end=cm.end())
            r = self.ref(bid, c, 0, "", c2, 0, "")
            st = "italic" if ital else "chapter-only"
            if c > bk.chapters or (c2 and c2 > bk.chapters):
                st = "invalid"
            hits.append(Hit(start, cm.end(), r, st, raw=text[start:cm.end()]))
            if not ital and st != "invalid":
                self._set_book(ctx, bid, seg_no)
                ctx.chapter = c2 or c
            return cm.end(), None, None
        # bare mention
        allowed = kind == "full" and (bare_ok or self.pt.intro_before.search(text[max(0, start - 25):start]))
        if allowed and not ital:
            self._set_book(ctx, bid, seg_no)
        return m.end(), None, None

    # -------------------------------------------------------------------------
    def _cv(self, text, italic, ctx, seg_no, hits, s, e, c1, v1, s1, x, y, s2, last_book, chain):
        pt, lang = self.pt, self.lang
        gap = text[last_book[1]:s] if last_book else None
        ital = _is_italic(italic, s, e, text)
        hit_start = s
        book = None
        if last_book and pt.attached_gap.match(gap):
            book = last_book[0]
            status = "italic" if (last_book[2] or ital) else "explicit"
            hit_start = last_book[3]
        elif chain and chain.get("book") is not None and pt.chain_gap.match(text[chain["end"]:s]):
            book = chain["book"]
            status = "chain" if chain["status"] == "explicit" else chain["status"]
            if ital and status != "citation":
                status = "italic"
        elif chain and chain.get("book") is None and chain["status"] == "citation" and \
                pt.chain_gap.match(text[chain["end"]:s]):
            status = "citation"
        else:
            pre = text[max(0, s - 60):s]
            if CITATION_BEFORE.search(pre):
                status = "citation"
            elif ctx.book is not None and (not lang.p.get("bare_requires_parens") or _in_parens(text, s)):
                book = ctx.book
                weak = ctx.stale or (seg_no - ctx.book_seg) > self.distant_after
                status = "inferred-weak" if weak else "inferred"
                if ital:
                    status = "italic"
            else:
                status = "unresolved"
        if book is None:
            hits.append(Hit(s, e, None, status, raw=text[s:e], reason="volume:page" if status == "citation" else ""))
            ch = dict(book=None, chapter=c1, status=status, end=e)
            return self._cont(text, e, None, c1, status, hits, ch), None, ch
        r = self.mkref(book, c1, v1, s1, x, y, s2)
        if not r.valid():
            status = "invalid"
        hits.append(Hit(hit_start, e, r, status, raw=text[hit_start:e]))
        end_ch = r.c2 if (r.c2 and r.c2 != r.c1) else r.c1
        if status in INDEXED_STATUSES:
            ctx.book, ctx.chapter = book, end_ch
        ch = dict(book=book, chapter=end_ch, status=status, end=e)
        return self._cont(text, e, book, end_ch, status, hits, ch), None, ch

    def _cont(self, text, pos, book, chapter, status, hits, chain):
        pt = self.pt
        while True:
            m = pt.cont.match(text, pos)
            if not m or not pt.cont_ok_after.match(text, m.end()):
                return pos
            bm = self.lang.book_re.match(text, m.start("v"))
            if bm and self.lang.resolve(bm.group("name")):
                return pos          # the number starts a book name ("und 1. Mose 1,1")
            if book is None:
                hits.append(Hit(m.start("v"), m.end(), None, status, raw=text[m.start("v"):m.end()],
                                reason="volume:page" if status == "citation" else ""))
            else:
                v2 = m.group("v2")
                r = self.ref(book, chapter, int(m.group("v")), m.group("s") or "",
                             chapter if v2 else 0, int(v2) if v2 else 0, m.group("s2") or "")
                st = "chain" if status == "explicit" else status
                if not r.valid():
                    st = "invalid"
                hits.append(Hit(m.start("v"), m.end(), r, st, raw=text[m.start("v"):m.end()]))
            chain["end"] = m.end()
            pos = m.end()


def parse_label(cat: Catalog, book: str, text: str) -> Ref | None:
    """Parse a hand-typed entry: "5:9-6:1", "3,16", "3:16a", "5:9-16", "Jude 5",
    or Hebrew numerals ("ג:טז")."""
    t = text.strip().replace("—", "-").replace("–", "-")
    bk = cat.get(book)

    def num(s):
        if s is None:
            return None
        return int(s) if s.isdigit() else heb_to_int(s)

    tok = r"(\d{1,3}|[" + HLET + "׳״'\"]{1,5})"
    m = re.fullmatch(tok + r"\s*[:,.]\s*" + tok + r"([a-d]|ff?\.?|ss?\.?)?(?:\s*-\s*" + tok +
                     r"(?:\s*[:,.]\s*" + tok + r")?([a-d]|ff?\.?|ss?\.?)?)?", t)
    if m:
        c1, v1 = num(m.group(1)), num(m.group(2))
        x, y = num(m.group(4)), num(m.group(5))
        if not c1 or not v1:
            return None
        s1, s2 = _norm_sfx(m.group(3)), _norm_sfx(m.group(6))
        if x is None:
            r = Ref(book, c1, v1, s1, cat=cat)
        elif y is not None:
            r = Ref(book, c1, v1, s1, x, y, s2, cat=cat)
        else:
            r = Ref(book, c1, v1, s1, c1, x, s2, cat=cat)
        return r if r.valid() else None
    m = re.fullmatch(tok + r"([a-d])?(?:\s*-\s*" + tok + r"([a-d])?)?", t)
    if m:
        a, b = num(m.group(1)), num(m.group(3))
        if not a:
            return None
        if bk.single_chapter:
            r = Ref(book, 1, a, m.group(2) or "", 1 if b else 0, b or 0, m.group(4) or "", cat=cat)
        elif not m.group(2) and not m.group(4):
            r = Ref(book, a, 0, "", b or 0, 0, "", cat=cat)
        else:
            return None
        return r if r.valid() else None
    return None
