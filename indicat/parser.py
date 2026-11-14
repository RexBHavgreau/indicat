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
    unknown-book   a word before the reference that isn't a known book name ("Geneses 3:15")
    check-name     a book name that is recognized but needs checking ("3 Kings" = 1 Kings)
    apocrypha      an Apocrypha reference while the Apocrypha is not indexed
    mt             the Hebrew (MT) number of a verse also cited by its English number
    f-end          "f" on the last verse of a chapter (no verse follows)
    manual         added by hand in the review table
    ocr            (PDF) read through an OCR slip: "Gen. l:l" = Genesis 1:1
    interrupted    (PDF) a word hyphenated across a page break ("Deu-‖143‖teronomy")

Indexed by default: explicit, chain, inferred, inferred-weak, check-name, mt, manual.
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

INDEXED_STATUSES = {"explicit", "chain", "inferred", "inferred-weak", "check-name", "mt", "manual", "ocr"}
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
    "unknown-book": "Unknown book name",
    "check-name": "Book name needs checking",
    "apocrypha": "Apocrypha (not indexed)",
    "mt": "Hebrew numbering (MT)",
    "f-end": "“f” at the end of a chapter",
    "manual": "Added by hand",
    # PDF route
    "ocr": "OCR reading corrected",
    "interrupted": "Possible interrupted term (not indexed)",
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


ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def roman_to_int(s: str) -> int | None:
    """Lower- or upper-case roman numeral (up to 399) -> int, or None if it isn't one."""
    t = (s or "").lower()
    if not t or any(c not in ROMAN_VALUES for c in t) or not (t == s or t.upper() == s):
        return None
    total, prev = 0, 0
    for c in reversed(t):
        v = ROMAN_VALUES[c]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total if 0 < total < 400 and _int_to_roman(total) == t else None


def _int_to_roman(n: int) -> str:
    out = ""
    for v, r in ((100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"),
                 (1, "i")):
        while n >= v:
            out += r
            n -= v
    return out


SFX_ORDER = {"": 0, "a": 1, "b": 2, "c": 3, "d": 4, "f": 5, "s": 5, "ff": 6, "ss": 6}


def _norm_sfx(s: str | None) -> str:
    return (s or "").rstrip(".").strip()


def expand_short(a: int, b: int) -> int:
    """A range written short: 16–7 means 16–17, 118–9 means 118–119."""
    sa, sb = str(a), str(b)
    if b < a and len(sb) < len(sa):
        full = int(sa[:len(sa) - len(sb)] + sb)
        if full > a:
            return full
    return b


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
    mt: bool = False                    # Hebrew (MT) numbering, printed with "[MT]"

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
        mt = " [MT]" if self.mt else ""
        start = f"{n(self.v1)}{self._sfx(self.s1)}" if single else f"{n(self.c1)}{sep}{n(self.v1)}{self._sfx(self.s1)}"
        if not self.c2:
            return start + mt
        if self.c2 == self.c1 or single:
            return f"{start}–{n(self.v2)}{self._sfx(self.s2)}{mt}"
        return f"{start}–{n(self.c2)}{sep}{n(self.v2)}{self._sfx(self.s2)}{mt}"

    def sort_key(self) -> str:
        """Canonical order within a book: 34, 34a, 34b, 34ff., 34–35, 34–36 …"""
        def sx(s):
            return str(SFX_ORDER.get(s, 0))
        end = f"{self.c2:03d}{self.v2:03d}{sx(self.s2)}" if self.c2 else "0000000"
        lead = "8" if self.c2 else sx(self.s1)
        return f"{self.c1:03d}{self.v1:03d}{lead}{sx(self.s1)}{end}" + ("M" if self.mt else "")

    def book_key(self) -> str:
        return self.cat.book_key(self.book)

    def display(self) -> str:
        return f"{self.book_name} {self.label()}"

    def fits(self, numbering: str = "any") -> bool:
        """Do the chapters and verses exist?  numbering: "eng", "orig" or "any"."""
        if not self.cat or self.book not in self.cat.books:
            return False
        bk = self.cat.get(self.book)
        for c, v in ((self.c1, self.v1), (self.c2, self.v2)):
            if c == 0:
                continue
            if c < 1 or c > bk.chapters or v > 176:
                return False
            mx = self.cat.verse_max(self.book, c, numbering)
            if mx is not None and (mx == 0 or v > mx):
                return False
        if self.c2 and (self.c2, self.v2) < (self.c1, self.v1):
            return False
        return True

    def valid(self) -> bool:
        return self.fits("any")


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
            sfx_alts.append(re.escape(s) + r"\.?(?![A-Za-zÀ-ÿ])")
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
        self.cv_next = re.compile(r"\.?" + SP + r"*\(?" + SP + r"*\d{1,3}" + self.sep + r"\d")
        self.hcv_next = re.compile(SP + r"*" + HN + SP + r"*[,:]" + SP + r"*" + HN) if self.hcv else None
        self.attached_gap = re.compile(r"^\.?" + SP + r"*\(?" + SP + r"*$")
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
        self.next_word = re.compile(SP + r"+([a-zà-ÿ][\w’']*)")
        self.author_verbs = set(p.get("author_verbs", []))
        self.person_books = set(p.get("person_books", []))
        self.not_books = set(p.get("not_books", []))
        self.unknown_before = re.compile(r"(?:^|[^\w’'])((?:[1-4]" + SP + r"?)?[A-ZÀ-Þ][a-zà-ÿ]{0,14}\.?)" + SP + r"*$")
        mtw = sorted(p.get("mt_words", []), key=len, reverse=True)
        self.mt_after = re.compile(SP + r"*(?:" + ("|".join(re.escape(w) for w in mtw) or "(?!)") +
                                   r")(?![A-Za-zÀ-ÿ])") if mtw else None
        self.bracket_alt = re.compile(SP + r"*\[" + SP + r"*$")
        # older citation styles (PDF route): "Matt. v. 3", "ch. iii. ver. 4"
        roman = r"(?:[ivxlc]{1,7}|[IVXLC]{1,7})"
        rng = r"(?:" + SP + "?" + DASH + SP + r"?(?P<v2>\d{1,3}))?(?!\d)(?![:.,]\d)"
        self.old_rc = re.compile(r"\.?" + SP + r"+(?P<rc>" + roman + r")\.?,?" + SP + r"*(?P<v>\d{1,3})" + rng)
        # a list after one: "Heb. iii. 7, ix. 8; x. 15–17", "Matt. v. 3, 9, vi. 9" (a roman numeral and a
        # period start a new chapter; a bare number is another verse of the same chapter)
        self.old_list = re.compile(SP + r"*[,;]" + SP + r"*(?:(?:and|&)" + SP + r"+)?(?P<item>(?:(?P<rc>" + roman +
                                   r")\." + SP + r"*)?(?P<v>\d{1,3})" + rng + r")")
        self.old_cw = re.compile(r"(?<![\w])(?:[Cc]h|[Cc]hap|[Cc]hapter)\.?" + SP + r"*(?P<c>" + roman +
                                 r"|\d{1,3})[.,]?" + SP + r"*(?:ver|vers|vs|v|verse)\.?" + SP + r"*(?P<v>\d{1,3})" +
                                 rng)


CITATION_BEFORE = re.compile(
    r"(?:\b(?:vols?|nos?|pp?|col|cols|Bd|Bde|S|Sp|t|tome)\." + SP + r"*\d*,?" + SP + r"*$"
    r"|\d{4}\)?[,.]?" + SP + r"*$"
    r"|\)[,.]?" + SP + r"*$"
    r"|\b[A-Z]{2,}[A-Za-z]*[,.]?" + SP + r"*$"
    r"|\b(?:ed|éd|Hg|hg)\.,?" + SP + r"*$)")
TIME_AFTER = re.compile(SP + r"?(?:o['’]clock|Uhr\b|h\b)")


AUTHOR_COMMA = re.compile(r"[A-ZÀ-Þ][\w’'\-]+," + SP + r"*$")


def _is_italic(italic: list, s: int, e: int, text: str = "") -> bool:
    """Is this span an italic *title* (not an italic quotation or emphasis)?"""
    if not italic or e <= s:
        return False
    span = italic[s:e]
    if not (span and all(span)):
        return False
    if text and AUTHOR_COMMA.search(text[max(0, s - 40):s]):
        return True                      # "Bock, Luke 1:1–9:50": a title after an author's name
    letters = [f for ch, f in zip(text, italic) if ch.isalpha()] if text else italic
    if letters and sum(letters) / len(letters) > 0.6:
        return False
    if text and re.search(r"[(\[;]" + SP + r"*(?:cf\.|vgl\." + SP + r"*)?$", text[max(0, s - 6):s]):
        return False
    return True


def _after_italic_title(text: str, italic: list, s: int) -> bool:
    """"…, The Catholic Encyclopedia, 5:188": a number right after an italic title and a comma."""
    if not italic:
        return False
    k = s - 1
    while k >= 0 and text[k] in "    ":
        k -= 1
    if k < 0 or text[k] != ",":
        return False
    k -= 1
    while k >= 0 and text[k] in "”’\"'":
        k -= 1
    if k < 0 or k >= len(italic) or not italic[k]:
        return False
    j = k
    while j > 0 and j - 1 < len(italic) and italic[j - 1]:
        j -= 1
    run = text[j:k + 1]
    return bool(re.search(r"(?:^|\s)[A-ZÀ-Þ]", run))


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
    def __init__(self, lang: Language, distant_after: int = 15, old_styles: bool = False):
        self.lang = lang
        self.cat = lang.cat
        self.pt = Patterns(lang)
        self.ctx = Context()
        self.distant_after = distant_after
        self.old_styles = old_styles and lang.code == "en"
        old = "(?P<old>" + self.pt.old_cw.pattern + ")|" if self.old_styles else ""
        self.master = re.compile(
            old + "(?P<book>" + lang.book_re.pattern + ")|(?P<cv>" + self.pt.cv.pattern + ")|(?P<vw>" +
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
        return self.ref(book, c1, v1, s1, c1, expand_short(v1, x), s2)

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
            if self.old_styles and m.group("old") is not None:
                pos = self._old_cw(m, text, italic, ctx, seg_no, hits)
                last_book = chain = None
                continue
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
                        v = int(im.group("v"))
                        r = self.ref(ctx.book, ctx.chapter, v, im.group("s") or "",
                                     ctx.chapter if v2 else 0, expand_short(v, int(v2)) if v2 else 0,
                                     im.group("s2") or "")
                        hits.append(Hit(is_, ie, r, "verse-only" if r.valid() else "invalid",
                                        raw=text[s:e], reason=f"chapter {ctx.chapter} assumed from context"))
                    else:
                        why = ("chapter unclear after a range of chapters" if ctx.book is not None
                               else "verse number with no chapter in context")
                        hits.append(Hit(is_, ie, None, "unresolved", raw=text[s:e], reason=why))
                chain = None
                last_book = None
                pos = e
                continue
            pos = m.end()
        flush(n + 1)
        self._post(text, hits)
        return hits, snaps

    # -------------------------------------------------------------------------
    def _post(self, text, hits):
        """f / ff, the Apocrypha, and the Hebrew (MT) number of a verse."""
        steps = dict(self.lang.p.get("suffixes", []))
        for h in hits:
            r = h.ref
            if r is None:
                continue
            if r.s1 and not r.c2 and r.v1 and steps.get(r.s1) == 1:
                mx = self.cat.verse_max(r.book, r.c1)
                if mx is not None and r.v1 >= mx:
                    if h.status in INDEXED_STATUSES:
                        h.status = "f-end"
                    h.reason = f"no verse follows {r.c1}{self.cat.label_sep}{r.v1} in this chapter"
                else:
                    sfx = r.s1
                    r.c2, r.v2, r.s1 = r.c1, r.v1 + 1, ""
                    h.reason = f"“{r.v1}{sfx}” read as {r.v1}–{r.v2}"
            elif r.s1 and steps.get(r.s1) == 99:
                h.reason = h.reason or "open-ended (" + r.s1 + ")"
            if h.status in INDEXED_STATUSES and not self.cat.ap_indexed and \
                    self.cat.books.get(r.book) and self.cat.get(r.book).section == "AP":
                h.status = "apocrypha"
        pt = self.pt
        for i, h in enumerate(hits):
            r = h.ref
            if r is None or not r.v1:
                continue
            # "Mal 3:23 [4:5]": the same verse in two numberings
            nxt = hits[i + 1] if i + 1 < len(hits) else None
            if nxt is not None and nxt.ref is not None and nxt.ref.v1 and \
                    pt.bracket_alt.match(text[h.end:nxt.start]) and text[nxt.end:nxt.end + 1] == "]":
                b = nxt.ref
                if b.book != r.book:
                    nxt.ref = b = Ref(r.book, b.c1, b.v1, b.s1, b.c2, b.v2, b.s2, self.cat)
                if nxt.status in ("inferred", "inferred-weak", "invalid") and b.valid():
                    nxt.status = "chain" if h.status == "explicit" else h.status
                if self.cat.get(r.book).section == "OT":
                    a_mt = (r.fits("orig") and not r.fits("eng")) or (b.fits("eng") and not b.fits("orig"))
                    mt_hit, other = (h, nxt) if a_mt else (nxt, h)
                    self._mark_mt(mt_hit)
                    other.reason = other.reason or "the same verse is also cited in Hebrew numbering"
                continue
            if pt.mt_after is not None and pt.mt_after.match(text, h.end) and \
                    self.cat.get(r.book).section == "OT":
                self._mark_mt(h)

    def _old_cw(self, m, text, italic, ctx, seg_no, hits):
        """ "ch. iii. ver. 4": chapter and verse words, the book from context."""
        s, e = m.start("old"), m.end("old")
        c = m.group("c")
        c = int(c) if c.isdigit() else roman_to_int(c)
        v = int(m.group("v"))
        v2 = m.group("v2")
        if not c:
            return e
        if ctx.book is None:
            hits.append(Hit(s, e, None, "unresolved", "chapter and verse with no book in context", raw=text[s:e]))
            return e
        r = self.ref(ctx.book, c, v, "", c if v2 else 0, expand_short(v, int(v2)) if v2 else 0, "")
        weak = ctx.stale or (seg_no - ctx.book_seg) > self.distant_after
        st = "inferred-weak" if weak else "inferred"
        if _is_italic(italic, s, e, text):
            st = "italic"
        if not r.valid():
            st = "invalid"
        hits.append(Hit(s, e, r, st, "older style: chapter and verse words", raw=text[s:e]))
        if st in INDEXED_STATUSES:
            ctx.chapter = c
        return e

    def _mark_mt(self, h):
        h.ref.mt = True
        if h.status in INDEXED_STATUSES:
            h.status = "mt"
        h.reason = "Hebrew (MT) numbering"

    # -------------------------------------------------------------------------
    def _book(self, m, text, italic, ctx, seg_no, hits):
        pt, lang = self.pt, self.lang
        name_s, name_e = m.start("name"), m.end("name")
        info = lang.resolve(m.group("name"))
        if info is None:
            return None
        start, end = m.start("book"), m.end("book")
        followed = (pt.cv_next.match(text, end) or pt.after_ch.match(text, end) or
                    (pt.hcv_next.match(text, end) if pt.hcv_next else None) or
                    (self._old_rc(text, end) if self.old_styles else None))
        if not followed:
            # back off to a shorter spelling that *is* followed by a number
            for cm, cinfo in lang.candidates_at(text, name_s)[1:]:
                ce = cm.end()
                if (pt.cv_next.match(text, ce) or pt.after_ch.match(text, ce) or
                        (pt.hcv_next.match(text, ce) if pt.hcv_next else None) or
                        (self._old_rc(text, ce) if self.old_styles else None)):
                    info, end, name_e = cinfo, ce, ce
                    break
        bid, kind, short, bare_ok = info
        bk = self.cat.get(bid)
        ital = _is_italic(italic, name_s, name_e, text)
        flag = lang.flag(text[name_s:name_e])
        named = "check-name" if flag else "explicit"

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
                    st = "italic" if ital else named
                    if not r.valid():
                        st = "invalid"
                    hits.append(Hit(start, hm.end(), r, st, flag, raw=text[start:hm.end()]))
                    if st in ("explicit", "check-name"):
                        self._set_book(ctx, bid, seg_no)
                        ctx.chapter = r.c2 if r.c2 and r.c2 != r.c1 else r.c1
                    return hm.end(), None, dict(book=bid, chapter=ctx.chapter, status=st, end=hm.end(), heb=True)

        om = self._old_rc(text, end) if self.old_styles else None
        if om:
            c, v = roman_to_int(om.group("rc")), int(om.group("v"))
            v2 = om.group("v2")
            r = self.ref(bid, c, v, "", c if v2 else 0, expand_short(v, int(v2)) if v2 else 0, "")
            if bk.single_chapter:
                r = None
            if r is not None:
                st = "italic" if ital else named
                if not r.valid():
                    st = "invalid"
                hits.append(Hit(start, om.end(), r, st, flag or "older style: roman chapter number",
                                raw=text[start:om.end()]))
                end_at = self._old_list(text, om.end(), bid, c, st, hits)
                c = hits[-1].ref.c1 if hits[-1].ref is not None else c
                if st in ("explicit", "check-name"):
                    self._set_book(ctx, bid, seg_no)
                    ctx.chapter = c
                return end_at, None, dict(book=bid, chapter=c, status=st, end=end_at)
        if pt.cv_next.match(text, end):
            if not ital:
                self._set_book(ctx, bid, seg_no)
            return end, (bid, end, ital, start, flag), None
        xm = pt.xch.match(text, end)
        if xm:
            r = self.ref(bid, int(xm.group("c")), 1, "", int(xm.group("x")), int(xm.group("y")), "")
            st = "italic" if ital else named
            if not r.valid():
                st = "invalid"
            hits.append(Hit(start, xm.end(), r, st, flag, raw=text[start:xm.end()]))
            if st in ("explicit", "check-name"):
                self._set_book(ctx, bid, seg_no)
                ctx.chapter = r.c2
            return xm.end(), None, dict(book=bid, chapter=r.c2, status=st, end=xm.end())
        cm = pt.after_ch.match(text, end)
        if cm and not short:
            c = int(cm.group("c"))
            c2 = int(cm.group("c2")) if cm.group("c2") else 0
            if bk.single_chapter:
                r = self.ref(bid, 1, c, "", 1 if c2 else 0, expand_short(c, c2) if c2 else 0, "")
                st = "italic" if ital else named
                if not r.valid():
                    st = "invalid"
                hits.append(Hit(start, cm.end(), r, st, flag, raw=text[start:cm.end()]))
                if not ital:
                    self._set_book(ctx, bid, seg_no)
                    ctx.chapter = 1
                return cm.end(), None, dict(book=bid, chapter=1, status=named if not ital else "italic",
                                            end=cm.end())
            r = self.ref(bid, c, 0, "", c2, 0, "")
            st = "italic" if ital else "chapter-only"
            if c > bk.chapters or (c2 and c2 > bk.chapters):
                st = "invalid"
            hits.append(Hit(start, cm.end(), r, st, raw=text[start:cm.end()]))
            if not ital and st != "invalid":
                self._set_book(ctx, bid, seg_no)
                ctx.chapter = None if (c2 and c2 != c) else c     # after "1 Kings 1–11" the chapter is unclear
            return cm.end(), None, None
        # bare mention
        if ital:
            return m.end(), None, None
        nw = pt.next_word.match(text, end) if kind == "full" else None
        if nw and nw.group(1) in pt.author_verbs:
            self._set_book(ctx, bid, seg_no)          # "Matthew uses δεῖ eight times (16:21)"
            return m.end(), None, None
        if nw and bid in pt.person_books:
            return m.end(), None, None                # "Zechariah responds with doubt (1:20)": a person
        allowed = kind == "full" and (bare_ok or self.pt.intro_before.search(text[max(0, start - 25):start]))
        if allowed:
            self._set_book(ctx, bid, seg_no)
        return m.end(), None, None

    # -------------------------------------------------------------------------
    def _old_list(self, text, pos, bid, chapter, status, hits) -> int:
        """The rest of a list after an older-style reference: "Heb. iii. 7, ix. 8, x. 15".  Returns where
        the list ends."""
        st = "chain" if status == "explicit" else status
        while True:
            lm = self.pt.old_list.match(text, pos)
            if not lm or self.lang.candidates_at(text, lm.start("item")):
                return pos                    # no list item, or a new book ("; 1 Paralip. xvi. 1")
            if lm.group("rc"):
                c = roman_to_int(lm.group("rc"))
                if not c:
                    return pos
                chapter = c
            v, v2 = int(lm.group("v")), lm.group("v2")
            r = self.ref(bid, chapter, v, "", chapter if v2 else 0, expand_short(v, int(v2)) if v2 else 0, "")
            hits.append(Hit(lm.start("item"), lm.end(), r, st if r.valid() else "invalid",
                            "older style: roman chapter number", raw=text[lm.start("item"):lm.end()]))
            pos = lm.end()

    def _old_rc(self, text, end):
        m = self.pt.old_rc.match(text, end)
        return m if m and roman_to_int(m.group("rc")) else None

    def _cv(self, text, italic, ctx, seg_no, hits, s, e, c1, v1, s1, x, y, s2, last_book, chain):
        pt, lang = self.pt, self.lang
        gap = text[last_book[1]:s] if last_book else None
        ital = _is_italic(italic, s, e, text)
        hit_start = s
        book = None
        reason = ""
        if last_book and pt.attached_gap.match(gap):
            book = last_book[0]
            status = "italic" if (last_book[2] or ital) else ("check-name" if last_book[4] else "explicit")
            reason = last_book[4]
            hit_start = last_book[3]
        elif chain and chain.get("book") is not None and pt.chain_gap.match(text[chain["end"]:s]):
            book = chain["book"]
            status = "chain" if chain["status"] == "explicit" else chain["status"]
            if ital and status != "citation":
                status = "italic"
        elif chain and chain.get("book") is None and chain["status"] in ("citation", "unknown-book") and \
                pt.chain_gap.match(text[chain["end"]:s]):
            status = chain["status"]
            reason = chain.get("reason", "")
        else:
            pre = text[max(0, s - 60):s]
            uk = pt.unknown_before.search(pre)
            if uk and (uk.group(1).rstrip(".").strip() in pt.not_books or lang.resolve(uk.group(1))):
                uk = None
            if uk and not uk.group(1).endswith("."):
                # "While 5:6 does…": an ordinary word starting a sentence, not a book name
                before = text[:max(0, s - 60) + uk.start(1)].rstrip(" \u00a0\u2009\u202f“‘\"'")
                if not before or before[-1] in ".!?…":
                    uk = None
            if CITATION_BEFORE.search(pre) or _after_italic_title(text, italic, s):
                status = "citation"
            elif uk:
                status = "unknown-book"
                reason = f"“{uk.group(1).strip()}” is not a book name Indicat knows"
            elif ctx.book is not None and (not lang.p.get("bare_requires_parens") or _in_parens(text, s)):
                book = ctx.book
                weak = ctx.stale or (seg_no - ctx.book_seg) > self.distant_after
                status = "inferred-weak" if weak else "inferred"
                if ital:
                    status = "italic"
            else:
                status = "unresolved"
        if book is None:
            if status == "citation":
                reason = "volume:page"
            hits.append(Hit(s, e, None, status, raw=text[s:e], reason=reason))
            ch = dict(book=None, chapter=c1, status=status, end=e, reason=reason)
            return self._cont(text, e, None, c1, status, hits, ch), None, ch
        r = self.mkref(book, c1, v1, s1, x, y, s2)
        if not r.valid():
            status = "invalid"
        hits.append(Hit(hit_start, e, r, status, reason, raw=text[hit_start:e]))
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
                                reason=chain.get("reason", "")))
            else:
                v2 = m.group("v2")
                v = int(m.group("v"))
                r = self.ref(book, chapter, v, m.group("s") or "",
                             chapter if v2 else 0, expand_short(v, int(v2)) if v2 else 0, m.group("s2") or "")
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
