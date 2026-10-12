"""Original-language word indexes and user term sets.

Three kinds of index besides Scripture:

* **Script word indexes** (Greek, Hebrew/Aramaic, Syriac): every word written
  in that alphabet is found by its characters alone.
* **Tagged-language word indexes** (Latin, German, ...): every word the
  manuscript tags with that language (Word: Review > Language).
* **Term sets**: lists the user supplies (TXT or CSV) with headings,
  subentries, the forms to match, sort-as text and See / See also.

Quotations are left out of the word indexes: paragraphs in a quotation style
(or indented prose paragraphs) are skipped whole, and inside running text a
stretch of more than `max_run` original-language words is treated as a
quotation unless it is a list (items separated by commas, semicolons or
slashes, each only a word or two long).  Skipped stretches are reported so
the user can bring them back.

Everything here is written so the InDesign script (js/terms.js) can do
exactly the same: character classes and folding come from tables that are
generated once and shipped to the script, and matching uses plain string
search rather than regular expressions.
"""
from __future__ import annotations

import bisect
import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Character tables (shared with the InDesign script through DATA)
# ---------------------------------------------------------------------------
FOLD_RANGES = [(0x41, 0x24F), (0x300, 0x36F), (0x370, 0x3FF), (0x400, 0x4FF), (0x590, 0x5FF),
               (0x700, 0x74F), (0x1DC0, 0x1DFF), (0x1E00, 0x1EFF), (0x1F00, 0x1FFF), (0xFB1D, 0xFB4F)]
SPACES = set(" \t\n\r              　")
# characters that are part of no word but may sit between the words of a quotation
GAP_PUNCT = set(",.;:··;׃־׀׆·!?‐‑-|")
LIST_SEPS = set(",;/،")
ELISION = set("’ʼ᾽'")
HEB_PREFIXES = "ובכלמהש"


def _build_tables():
    lower, strip, marks = {}, {}, {}
    word_ranges = []
    for a, b in FOLD_RANGES + [(0x30, 0x39)]:
        for cp in range(a, b + 1):
            c = chr(cp)
            cat = unicodedata.category(c)
            if cat == "Cn":
                continue
            if cat[0] in "LMN":
                word_ranges.append(cp)
            lo = c.lower()
            if len(lo) != 1:
                lo = c
            if lo == "ς":
                lo = "σ"
            if lo != c:
                lower[c] = lo
            nm = sum(1 for ch in unicodedata.normalize("NFD", c) if unicodedata.category(ch) == "Mn")
            if nm:
                marks[c] = nm
            st = "".join(ch for ch in unicodedata.normalize("NFD", c) if unicodedata.category(ch) != "Mn")
            st = unicodedata.normalize("NFC", st)
            if st != c:
                strip[c] = st
    # compress word chars into ranges
    ranges = []
    for cp in sorted(set(word_ranges)):
        if ranges and ranges[-1][1] == cp - 1:
            ranges[-1][1] = cp
        else:
            ranges.append([cp, cp])
    return lower, strip, ranges, marks


def _script_table():
    """[[start, end, script, kind]] with kind "L" (letter) or "M" (mark)."""
    rows = []

    def add(a, b, script):
        for cp in range(a, b + 1):
            c = chr(cp)
            cat = unicodedata.category(c)
            if cat == "Cn":
                continue
            if cat[0] == "L":
                kind = "L"
            elif cat == "Mn":
                kind = "M"
            else:
                continue
            if rows and rows[-1][2] == script and rows[-1][3] == kind and rows[-1][1] == cp - 1:
                rows[-1][1] = cp
            else:
                rows.append([cp, cp, script, kind])

    add(0x300, 0x36F, "*")             # combining marks attach to any script word
    add(0x370, 0x3FF, "greek")
    add(0x1F00, 0x1FFF, "greek")
    add(0x591, 0x5C7, "hebrew")
    add(0x5D0, 0x5F2, "hebrew")
    rows.append([0x5F3, 0x5F4, "hebrew", "L"])   # geresh, gershayim (abbreviations)
    add(0xFB1D, 0xFB4F, "hebrew")
    add(0x710, 0x74F, "syriac")
    rows.sort(key=lambda r: r[0])
    return rows


LOWER, STRIP, WORD_RANGES, MARKS = _build_tables()
SCRIPT_ROWS = _script_table()
_WR_STARTS = [r[0] for r in WORD_RANGES]
_SR_STARTS = [r[0] for r in SCRIPT_ROWS]


def is_word_char(c: str) -> bool:
    cp = ord(c)
    i = bisect.bisect_right(_WR_STARTS, cp) - 1
    return i >= 0 and WORD_RANGES[i][0] <= cp <= WORD_RANGES[i][1]


def is_letter(c: str) -> bool:
    return is_word_char(c) and not ("0" <= c <= "9")


def script_of(c: str):
    """(script, kind) or (None, None).  Script "*" = a combining mark of any script."""
    cp = ord(c)
    i = bisect.bisect_right(_SR_STARTS, cp) - 1
    if i >= 0 and SCRIPT_ROWS[i][0] <= cp <= SCRIPT_ROWS[i][1]:
        return SCRIPT_ROWS[i][2], SCRIPT_ROWS[i][3]
    return None, None


def fold_char(c: str, case: bool, marks: bool) -> str:
    s = LOWER.get(c, c) if case else c
    if marks:
        s = "".join(STRIP.get(ch, ch) for ch in s)
    return s


def fold(text: str, case: bool = True, marks: bool = True):
    """Folded text plus maps back to the original.

    Returns (ftext, starts, ends): ftext[j] came from text[starts[j]], and the
    original span of ftext[j] ends at ends[j] (marks dropped after a letter
    are counted with it).  Runs of white space become one space.
    """
    out, starts, ends = [], [], []
    prev_space = False
    for i, c in enumerate(text):
        if c in SPACES:
            if prev_space:
                ends[-1] = i + 1
                continue
            out.append(" ")
            starts.append(i)
            ends.append(i + 1)
            prev_space = True
            continue
        prev_space = False
        s = fold_char(c, case, marks)
        if not s:
            if ends:
                ends[-1] = i + 1
            continue
        for ch in s:
            out.append(ch)
            starts.append(i)
            ends.append(i + 1)
    return "".join(out), starts, ends


def fold_str(s: str, case: bool = True, marks: bool = True) -> str:
    return fold(s, case, marks)[0].strip(" ")


GREEK_ORDER = "αβγδεζηθικλμνξοπρστυφχψω"
HEB_ORDER = "אבגדהוזחטיכלמנסעפצקרשת"
HEB_FINALS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}


def sort_code(s: str) -> str:
    """Sort key safe for Word's \\y and InDesign's sortOrder: Greek and Hebrew
    letters become two-digit alphabet positions, Latin text stays as is."""
    k = fold_str(s)
    if not any(script_of(c)[0] in ("greek", "hebrew", "syriac") for c in k):
        return k
    out = []
    for c in k:
        c = HEB_FINALS.get(c, c)
        if c in GREEK_ORDER:
            out.append(f"{GREEK_ORDER.index(c) + 10:02d}")
        elif c in HEB_ORDER:
            out.append(f"{HEB_ORDER.index(c) + 10:02d}")
        elif script_of(c)[0] == "syriac":
            out.append(f"{ord(c) - 0x700 + 100:03d}")
        elif c == " ":
            out.append("00")
        else:
            out.append("99")
    return "".join(out)


def js_tables() -> dict:
    """The tables, in the form the InDesign script reads them."""
    return {"lower": LOWER, "strip": STRIP, "marks": MARKS, "word": WORD_RANGES, "script": SCRIPT_ROWS,
            "spaces": "".join(sorted(SPACES)), "gap": "".join(sorted(GAP_PUNCT)),
            "listSeps": "".join(sorted(LIST_SEPS)), "elision": "".join(sorted(ELISION)),
            "hebPrefixes": HEB_PREFIXES}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
GREEK_SKIP_03 = ("ο η το του της τω τη τον την οι αι τα των τοις ταις τους τας και δε τε γαρ ουν "
                 "μεν αλλα αλλ ει εν εις εκ εξ επι προς δια κατα μετα απο υπο περι παρα οτι ινα "
                 "ως ου ουκ ουχ μη αυτος αυτου αυτω αυτον αυτη αυτης αυτην αυτων αυτοις αυτους")
GREEK_SKIP = (GREEK_SKIP_03 +
              # personal pronouns
              " εγω μου εμου μοι εμοι με εμε ημεις ημων ημιν ημας συ σου σοι σε υμεις υμων υμιν υμας"
              # τίς / τί
              " τις τι τινος τινι τινα τινες τινων τισι τισιν"
              # εἰμί
              " ειμι ει εστιν εστι εσμεν εστε εισιν εισι ην ημην ησθα ημεν ητε ησαν εσομαι εση εσται"
              " εσομεθα εσεσθε εσονται ειναι ων ουσα ον οντος ουσης οντι ουση οντα ουσαν οντες ουσαι"
              " οντων ουσων ουσι ουσιν ουσας ω ης ωμεν ητε ωσιν ωσι ειη ισθι εστω εστωσαν"
              # elided prepositions and particles (also matched through ELIDED)
              " δι κατ καθ μετ μεθ απ αφ επ εφ υπ υφ παρ")
# elided forms -> the full word (folded), so δι’ is treated like διά
ELIDED = {"δι": "δια", "αλλ": "αλλα", "κατ": "κατα", "καθ": "κατα", "μετ": "μετα", "μεθ": "μετα",
          "απ": "απο", "αφ": "απο", "επ": "επι", "εφ": "επι", "υπ": "υπο", "υφ": "υπο", "παρ": "παρα"}

SCRIPT_INDEXES = {
    "hebrew": {"label": "Hebrew and Aramaic words", "title": "Index of Hebrew and Aramaic Words",
               "letter": "H", "short": "Hebrew",
               "skip": "את אשר כי על אל לא כל גם אם מן עם הוא היא הם הן זה זאת"},
    "greek": {"label": "Greek words", "title": "Index of Greek Words", "letter": "G", "short": "Greek",
              "skip": GREEK_SKIP},
    "syriac": {"label": "Syriac words", "title": "Index of Syriac Words", "letter": "Y", "short": "Syriac",
               "skip": ""},
}
SCRIPT_ORDER = ["hebrew", "greek", "syriac"]
# languages offered for tagged-language indexes: code -> (name, default title, InDesign names, skip list)
TAGGED_LANGUAGES = {
    "la": ("Latin", "Index of Latin Words", ["Latin"],
           "et in est ad cum non ut de quod qui quae sed ab ex per atque ac vel aut si"),
    "de": ("German", "Index of German Words", ["German"], "der die das und ist in zu den von mit"),
    "fr": ("French", "Index of French Words", ["French"], "le la les de des et un une en du"),
    "nl": ("Dutch", "Index of Dutch Words", ["Dutch"], "de het een en van in is"),
    "es": ("Spanish", "Index of Spanish Words", ["Spanish"], "el la los las de y en un una que"),
    "pt": ("Portuguese", "Index of Portuguese Words", ["Portuguese"], "o a os as de e em um uma que"),
    "it": ("Italian", "Index of Italian Words", ["Italian"], "il la le di e in un una che"),
    "en": ("English", "Index of English Words", ["English"], "the and of to in a is"),
}
SEE_WORDS = {"en": ("See", "See also"), "es": ("Véase", "Véase también"), "pt": ("Ver", "Ver também"),
             "fr": ("Voir", "Voir aussi"), "de": ("Siehe", "Siehe auch"), "he": ("ראו", "ראו גם")}
TERM_LETTERS = "BCDEFJKLMPQRTUVWZ"
SCRIPTURE_LETTERS = {None, "", "O", "A", "N", "X", "S", "I"}

DEFAULT_WORDS = {
    "group_forms": True,          # group forms that differ only in accents / breathings / vowel points
    "dictionary_forms": True,     # Greek and Hebrew: file every form under its dictionary form (lemma)
    "forms_as_subentries": False, # ...and list the printed forms as subentries under it
    "skip_block_quotes": True,    # skip paragraphs in a quotation style, and indented prose paragraphs
    "max_run": 4,                 # a longer stretch of words is a quotation...
    "list_item_max": 2,           # ...unless it is a list of items this short
    "min_letters": 2,
    "scripts": {k: {"enabled": False, "title": v["title"], "skip": v["skip"]} for k, v in SCRIPT_INDEXES.items()},
    "tagged": [],                 # [{"lang": "la", "enabled": bool, "title": str, "skip": str}]
}

TERM_SET_OPTIONS = {
    "case_sensitive": False,
    "ignore_marks": True,         # accents, breathings, vowel points
    "whole_words": True,
    "plurals": False,             # also match -s / -es
    "hebrew_prefixes": False,     # also match with ו ה ב כ ל מ ש in front
    "skip_block_quotes": True,
}


def words_settings(s: dict) -> dict:
    """The word-index settings with defaults filled in (does not modify s)."""
    import copy
    cur = s.get("words") or {}
    out = copy.deepcopy(DEFAULT_WORDS)
    for k, v in cur.items():
        if k == "scripts":
            for sk, sv in v.items():
                out["scripts"].setdefault(sk, {}).update(sv)
        else:
            out[k] = v
    return out


def new_set_id(existing) -> str:
    n = 1
    ids = {x.get("id") for x in existing}
    while f"set{n}" in ids:
        n += 1
    return f"set{n}"


# ---------------------------------------------------------------------------
# Index registry
# ---------------------------------------------------------------------------
@dataclass
class IndexDef:
    id: str                 # "scripture" | "script:greek" | "lang:la" | "set:set1"
    kind: str               # scripture | script | lang | terms
    title: str
    short: str
    letter: str | None = None
    opts: dict = field(default_factory=dict)
    entries: list = field(default_factory=list)


def index_defs(settings: dict, include_disabled: bool = False, messages: list | None = None) -> list[IndexDef]:
    """The extra (non-Scripture) indexes switched on, in document order."""
    ws = words_settings(settings)
    out = []
    code = settings.get("language", "en")
    for key in SCRIPT_ORDER:
        sc = ws["scripts"].get(key, {})
        info = SCRIPT_INDEXES[key]
        if not (sc.get("enabled") or include_disabled):
            continue
        if key == "hebrew" and code == "he" and not include_disabled:
            if messages is not None:
                messages.append("The Hebrew word index is off because the book itself is in Hebrew; "
                                "use a term set for the words you want indexed.")
            continue
        out.append(IndexDef(f"script:{key}", "script", sc.get("title") or info["title"], info["short"],
                            info["letter"], {"skip": sc.get("skip", info["skip"]), "script": key}))
    pool = [c for c in TERM_LETTERS]
    for t in ws.get("tagged", []):
        if not (t.get("enabled") or include_disabled):
            continue
        lang = t.get("lang", "")
        name, title, idnames, skip = TAGGED_LANGUAGES.get(lang, (lang, f"Index of {lang} Words", [lang], ""))
        out.append(IndexDef(f"lang:{lang}", "lang", t.get("title") or title, name, pool.pop(0) if pool else None,
                            {"skip": t.get("skip", skip), "lang": lang, "idnames": idnames}))
    for ts in settings.get("term_sets", []):
        if not (ts.get("enabled") or include_disabled):
            continue
        opts = dict(TERM_SET_OPTIONS)
        opts.update(ts.get("options", {}))
        out.append(IndexDef(f"set:{ts.get('id')}", "terms", ts.get("title") or ts.get("name", "Index"),
                            ts.get("name", "Terms"), pool.pop(0) if pool else None, opts,
                            ts.get("entries", [])))
    return out


# ---------------------------------------------------------------------------
# Index entries
# ---------------------------------------------------------------------------
@dataclass
class TermRef:
    """An entry in a word or term index.  Shaped like parser.Ref where the
    rest of the app expects one (book_name = heading, label() = subentry)."""
    index: str
    heading: str
    sub: str = ""
    sort: str = ""
    sub_sort: str = ""
    key: str = ""             # grouping key for words ("lex:<script>:<n>" when filed under a dictionary form)
    cat: object = field(default=None, repr=False, compare=False)
    note: str = ""            # why the dictionary form is uncertain

    @property
    def book_name(self) -> str:
        return self.heading

    @property
    def book(self) -> str:
        return self.heading

    def label(self) -> str:
        return self.sub

    def display(self) -> str:
        return f"{self.heading}, {self.sub}" if self.sub else self.heading

    def yomi(self) -> str:
        h = self.sort or sort_code(self.heading)
        if self.sub:
            return f"{h}:{self.sub_sort or sort_code(self.sub)}"
        return h

    def as_list(self) -> list:
        return [self.index, self.heading, self.sub]


@dataclass
class TermHit:
    index: str
    start: int
    end: int
    status: str                 # word | term | quotation
    ref: TermRef | None
    reason: str = ""
    words: list = field(default_factory=list)    # for quotations: [(start, end, TermRef)]

    @property
    def raw(self) -> str:
        return self.ref.display() if self.ref else ""


@dataclass
class SegMeta:
    quote: str | None = None        # "style" | "indent" | None
    table: bool = False
    langs: list | None = None       # per-character language tag (or None)


QUOTE_STYLE_RE = re.compile(r"quot|block|extract|cita|zitat|epigra|excerpt|ציטוט", re.I)
INDENT_PROSE_WORDS = 12            # an indented paragraph this long counts as a block quotation


def count_words(text: str) -> int:
    n, inw = 0, False
    for c in text:
        w = is_word_char(c)
        if w and not inw:
            n += 1
        inw = w
    return n


def is_block_quote(text: str, meta: SegMeta) -> bool:
    if meta.table or not meta.quote:
        return False
    if meta.quote == "style":
        return True
    return count_words(text) >= INDENT_PROSE_WORDS


# ---------------------------------------------------------------------------
# Tokenizing words of one script or one tagged language
# ---------------------------------------------------------------------------
def script_tokens(text: str, script: str) -> list[tuple[int, int]]:
    toks = []
    i, n = 0, len(text)
    while i < n:
        sc, kind = script_of(text[i])
        if sc == script and kind == "L":
            j = i + 1
            while j < n:
                sc2, k2 = script_of(text[j])
                if sc2 == script or (sc2 == "*" and k2 == "M"):
                    j += 1
                    continue
                if text[j] in ELISION and script == "greek":
                    nxt = script_of(text[j + 1])[0] if j + 1 < n else None
                    if nxt != "greek":
                        j += 1        # elided word: δι’, ἀλλ’
                    break
                break
            toks.append((i, j))
            i = j
        else:
            i += 1
    return toks


def lang_tokens(text: str, langs: list | None, lang: str) -> list[tuple[int, int]]:
    if not langs:
        return []
    toks = []
    i, n = 0, len(text)

    def ok(k):
        t = langs[k] if k < len(langs) else None
        return bool(t) and t.split("-")[0].lower() == lang

    while i < n:
        c = text[i]
        if is_letter(c) and ok(i):
            j = i + 1
            while j < n and is_letter(text[j]) and ok(j):
                j += 1
            # a word only partly in the language is not taken
            before = i > 0 and is_word_char(text[i - 1])
            after = j < n and is_word_char(text[j])
            if not before and not after:
                toks.append((i, j))
            i = j
        else:
            i += 1
    return toks


def _gap_ok(gap: str) -> bool:
    return 0 < len(gap) <= 6 and all(c in SPACES or c in GAP_PUNCT for c in gap)


def runs_of(text: str, toks: list) -> list[list]:
    """Group tokens into runs: words joined only by spaces and punctuation."""
    runs = []
    for t in toks:
        if runs and _gap_ok(text[runs[-1][-1][1]:t[0]]):
            runs[-1].append(t)
        else:
            runs.append([t])
    return runs


def classify_run(text: str, run: list, max_run: int, list_item_max: int) -> str:
    """"words" (index them) or "quotation" (skip)."""
    if len(run) <= max_run:
        return "words"
    items, cur = [], 1
    for a, b in zip(run, run[1:]):
        gap = text[a[1]:b[0]]
        if any(c in LIST_SEPS for c in gap):
            items.append(cur)
            cur = 1
        else:
            cur += 1
    items.append(cur)
    if len(items) >= 2 and max(items) <= list_item_max:
        return "words"
    return "quotation"


# ---------------------------------------------------------------------------
# Term sets: compiling and matching
# ---------------------------------------------------------------------------
@dataclass
class CompiledSet:
    d: IndexDef
    forms: list            # [(folded form, TermRef)] longest first
    crossrefs: list        # [(TermRef, "see"|"see_also", target)]


def compile_set(d: IndexDef) -> CompiledSet:
    o = d.opts
    case, marks = not o.get("case_sensitive"), bool(o.get("ignore_marks", True))
    forms, xrefs, seen = [], [], set()
    for e in d.entries:
        h = (e.get("heading") or "").strip()
        if not h:
            continue
        sub = (e.get("sub") or "").strip()
        ref = TermRef(d.id, h, sub, (e.get("sort") or "").strip(), (e.get("sub_sort") or "").strip())
        see = (e.get("see") or "").strip()
        also = (e.get("see_also") or "").strip()
        if see:
            xrefs.append((ref, "see", see))
            continue
        if also:
            xrefs.append((ref, "see_also", also))
        fl = [f for f in (e.get("forms") or []) if f and f.strip()]
        if not fl:
            fl = [sub or h]
        for f in fl:
            ff = fold_str(f, case, marks)
            if ff and (ff, ref.display()) not in seen:
                seen.add((ff, ref.display()))
                forms.append((ff, ref))
    forms.sort(key=lambda x: -len(x[0]))
    return CompiledSet(d, forms, xrefs)


def match_set(cs: CompiledSet, text: str, meta: SegMeta, cache: dict) -> list[TermHit]:
    o = cs.d.opts
    case, marks = not o.get("case_sensitive"), bool(o.get("ignore_marks", True))
    key = (case, marks)
    if key not in cache:
        cache[key] = fold(text, case, marks)
    ft, starts, ends = cache[key]
    whole, plurals, prefixes = o.get("whole_words", True), o.get("plurals"), o.get("hebrew_prefixes")
    cands = []
    for form, ref in cs.forms:
        pos = 0
        while True:
            j = ft.find(form, pos)
            if j < 0:
                break
            pos = j + 1
            s, e = j, j + len(form)
            if whole:
                if s > 0 and is_word_char(ft[s - 1]):
                    ok = False
                    if prefixes:
                        k = s
                        while k > 0 and s - k < 3 and ft[k - 1] in HEB_PREFIXES:
                            k -= 1
                            if k == 0 or not is_word_char(ft[k - 1]):
                                ok = True
                                s = k
                                break
                    if not ok:
                        continue
                if plurals and form[-1:].isascii() and form[-1:].isalpha():
                    if ft[e:e + 2] == "es" and (e + 2 >= len(ft) or not is_word_char(ft[e + 2])):
                        e += 2
                    elif ft[e:e + 1] == "s" and (e + 1 >= len(ft) or not is_word_char(ft[e + 1])):
                        e += 1
                if e < len(ft) and is_word_char(ft[e]):
                    continue
            cands.append((s, e, ref))
    cands.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    hits, last = [], -1
    skip = o.get("skip_block_quotes", True) and is_block_quote(text, meta)
    for s, e, ref in cands:
        if s < last:
            continue
        last = e
        a, b = starts[s], ends[e - 1]
        if skip:
            hits.append(TermHit(cs.d.id, a, b, "quotation", ref, "in a block quotation"))
        else:
            hits.append(TermHit(cs.d.id, a, b, "term", ref))
    return hits


# ---------------------------------------------------------------------------
# Dictionary forms (Hebrew: OSHB lemmas / Strong's headwords; Greek: MorphGNT)
# ---------------------------------------------------------------------------
LEX_SCRIPTS = ("hebrew", "greek")
CANTILLATION = set(range(0x0591, 0x05B0)) | {0x05BD, 0x05BF, 0x05C0, 0x05C3, 0x05C4, 0x05C5, 0x05C6}
LEX_DROP = set("/־\u200d\u200c\u034f")


def _decomp_tables():
    """Full canonical decomposition of every Greek and Hebrew character, and the
    combining class of every mark, so the InDesign script can build the same keys."""
    dec, ccc = {}, {}
    for a, b in ((0x370, 0x3FF), (0x1F00, 0x1FFF), (0x590, 0x5FF), (0xFB1D, 0xFB4F), (0x300, 0x36F)):
        for cp in range(a, b + 1):
            c = chr(cp)
            d = unicodedata.normalize("NFD", c)
            if d != c:
                dec[c] = d
            for ch in d:
                k = unicodedata.combining(ch)
                if k:
                    ccc[ch] = k
    return dec, ccc


DECOMP, CCC = _decomp_tables()


def lex_key(form: str, script: str) -> str:
    """The pointed lookup key: decomposed, lower case, grave = acute, ς = σ (Greek);
    cantillation dropped, qamats qatan = qamats (Hebrew); marks in canonical order."""
    chars = []
    for c in form:
        for ch in DECOMP.get(c, c):
            cp = ord(ch)
            if ch in LEX_DROP or ch in ELISION:
                continue
            if script == "hebrew":
                if cp in CANTILLATION:
                    continue
                if ch == "\u05c7":
                    ch = "\u05b8"
            else:
                ch = LOWER.get(ch, ch)
                if ch == "\u0300":
                    ch = "\u0301"
            chars.append(ch)
    # canonical ordering of each run of marks (stable sort by combining class)
    out, i = [], 0
    while i < len(chars):
        if CCC.get(chars[i]):
            j = i
            while j < len(chars) and CCC.get(chars[j]):
                j += 1
            out.extend(sorted(chars[i:j], key=lambda ch: CCC[ch]))
            i = j
        else:
            out.append(chars[i])
            i += 1
    return "".join(out)


_LEXICON: dict | None = None


def lexicon() -> dict:
    """{script: {"lemmas": [...], "pointed": {key: "ids"}, "plain": {key: "ids"}}}"""
    global _LEXICON
    if _LEXICON is None:
        import json
        from .catalog import data_dir
        _LEXICON = {}
        try:
            raw = json.loads((data_dir() / "lexicon.json").read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        for sc in LEX_SCRIPTS:
            x = raw.get(sc)
            if not x:
                continue
            _LEXICON[sc] = {"lemmas": x["lemmas"],
                            "pointed": {lex_key(k, sc): v for k, v in x["pointed"].items()},
                            "plain": x["plain"]}
    return _LEXICON


def lemma_ids(script: str, form: str, folded: str | None = None) -> list[int]:
    """Dictionary-form ids for a printed form: [] unknown, [n] certain, [n, m, …] unclear."""
    lex = lexicon().get(script)
    if not lex:
        return []
    ids = lex["pointed"].get(lex_key(form, script))
    if ids is None:
        ids = lex["plain"].get(folded if folded is not None else fold_str(form))
    return [int(x) for x in ids.split(",")] if ids else []


# ---------------------------------------------------------------------------
# The engine: one object per scan
# ---------------------------------------------------------------------------
class TermEngine:
    def __init__(self, settings: dict, defs: list[IndexDef] | None = None):
        self.ws = words_settings(settings)
        self.defs = defs if defs is not None else index_defs(settings)
        self.sets = [compile_set(d) for d in self.defs if d.kind == "terms"]
        self.skip = {}
        for d in self.defs:
            if d.kind in ("script", "lang"):
                self.skip[d.id] = {fold_str(w) for w in re.split(r"[\s,]+", d.opts.get("skip", "")) if w}

    @property
    def active(self) -> bool:
        return bool(self.defs)

    def _word_ref(self, d: IndexDef, text: str, s: int, e: int):
        form = text[s:e]
        key_full = fold_str(form)
        script = d.opts.get("script")
        elided = ""
        if script == "greek" and key_full and key_full[-1] in ELISION:
            bare = key_full.rstrip("".join(ELISION))
            elided = ELIDED.get(bare, "")
            key_full = elided or bare
        letters = sum(1 for c in key_full if is_letter(c))
        skip = self.skip.get(d.id, ())
        if letters < self.ws["min_letters"] or key_full in skip:
            return None
        key = key_full if self.ws["group_forms"] else fold_str(form, True, False)
        if script in LEX_SCRIPTS and self.ws.get("dictionary_forms", True):
            ids = lemma_ids(script, form, key_full)
            if ids:
                lemmas = lexicon()[script]["lemmas"]
                single = [i for i in ids if not re.search(r"[\s\u05be]", lemmas[i])]
                ids = single or ids                      # most frequent first
                lem = lemmas[ids[0]]
                if fold_str(lem) in skip:
                    return None
                sub = form if self.ws.get("forms_as_subentries") else ""
                note = ""
                if len(ids) > 1:
                    note = f"filed under {lem}; could also be " + " or ".join(lemmas[i] for i in ids[1:3])
                return TermRef(d.id, lem, sub, "", sort_code(sub) if sub else "", f"lex:{script}:{ids[0]}",
                               note=note)
        return TermRef(d.id, form, "", "", "", key)

    def scan(self, text: str, meta: SegMeta | None = None) -> list[TermHit]:
        meta = meta or SegMeta()
        out: list[TermHit] = []
        block = self.ws["skip_block_quotes"] and is_block_quote(text, meta)
        for d in self.defs:
            if d.kind == "terms":
                continue
            if d.kind == "script":
                toks = script_tokens(text, d.opts["script"])
            else:
                toks = lang_tokens(text, meta.langs, d.opts["lang"])
            if not toks:
                continue
            if block:
                runs = [toks]
            else:
                runs = runs_of(text, toks)
            for run in runs:
                kind = "quotation" if block else classify_run(text, run, int(self.ws["max_run"]),
                                                               int(self.ws["list_item_max"]))
                refs = [(s, e, self._word_ref(d, text, s, e)) for s, e in run]
                if kind == "words":
                    for s, e, r in refs:
                        if r is not None:
                            out.append(TermHit(d.id, s, e, "word-check" if r.note else "word", r, r.note))
                else:
                    words = [(s, e, r) for s, e, r in refs if r is not None]
                    if not words:
                        continue
                    reason = ("in a block quotation" if block else
                              f"part of a {len(run)}-word quotation")
                    out.append(TermHit(d.id, run[0][0], run[-1][1], "quotation", None, reason, words))
        cache: dict = {}
        for cs in self.sets:
            out.extend(match_set(cs, text, meta, cache))
        out.sort(key=lambda h: (h.start, h.end))
        return out


def choose_headings(refs: list[TermRef]) -> None:
    """Give every word in a group the same heading: the form with the most
    accents or vowel points, then one starting lower-case, then the most frequent."""
    groups: dict = {}
    for i, r in enumerate(refs):
        if r.key.startswith("lex:"):          # filed under its dictionary form already
            r.sort = sort_code(r.heading)
            continue
        groups.setdefault((r.index, r.key), []).append((i, r))
    for items in groups.values():
        stats: dict = {}
        for i, r in items:
            st = stats.setdefault(r.heading, [0, i])
            st[0] += 1
        def score(form):
            marks = sum(MARKS.get(c, 0) for c in form)
            c0 = form[:1]
            lower_first = 1 if (c0 not in LOWER or c0 == "ς") else 0
            return (-marks, -lower_first, -stats[form][0], stats[form][1])
        best = min(stats, key=score)
        full = fold_str(best)
        key = items[0][1].key
        tie = "" if key == full else "." + "".join(f"{ord(c):04x}" for c in key)
        for _, r in items:
            r.heading = best
            r.sort = sort_code(best) + tie


# ---------------------------------------------------------------------------
# Reading and writing term set files
# ---------------------------------------------------------------------------
CSV_COLUMNS = ["heading", "subentry", "match forms", "sort as", "see", "see also"]
_HEADER_ALIASES = {
    "heading": "heading", "main heading": "heading", "term": "heading", "entry": "heading",
    "subentry": "sub", "sub-entry": "sub", "sub entry": "sub", "subheading": "sub",
    "match forms": "forms", "forms": "forms", "match": "forms", "variants": "forms",
    "sort as": "sort", "sort": "sort", "see": "see", "see also": "see_also",
}


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            t = data.decode(enc)
            if enc == "utf-16" and "\x00" in t:
                continue
            return t
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def _split_forms(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split("|") if x.strip()]


def read_term_file(path: str | Path) -> tuple[list[dict], list[str]]:
    """Entries from a .txt (one term per line, variants after |) or .csv file.
    Returns (entries, problems)."""
    path = Path(path)
    text = _read_text(path)
    problems: list[str] = []
    entries: list[dict] = []
    if path.suffix.lower() == ".csv" or path.suffix.lower() == ".tsv":
        dialect = "excel-tab" if path.suffix.lower() == ".tsv" or ("\t" in text.split("\n", 1)[0]
                                                                   and "," not in text.split("\n", 1)[0]) else "excel"
        rows = list(csv.reader(io.StringIO(text), dialect=dialect))
        if not rows:
            return [], ["The file is empty."]
        cols = None
        first = [c.strip().lower() for c in rows[0]]
        if first and first[0] in _HEADER_ALIASES:
            cols = [_HEADER_ALIASES.get(c) for c in first]
            rows = rows[1:]
        else:
            cols = ["heading", "sub", "forms", "sort", "see", "see_also"]
        for n, row in enumerate(rows, start=2 if cols else 1):
            if not row or not any(c.strip() for c in row) or row[0].strip().startswith("#"):
                continue
            e = {"heading": "", "sub": "", "forms": [], "sort": "", "see": "", "see_also": ""}
            for c, v in zip(cols, row):
                if not c:
                    continue
                if c == "forms":
                    e["forms"] = _split_forms(v)
                else:
                    e[c] = v.strip()
            if not e["heading"]:
                problems.append(f"Row {n}: no heading, skipped.")
                continue
            entries.append(e)
    else:
        for n, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            forms = _split_forms(line)
            if not forms:
                continue
            entries.append({"heading": forms[0], "sub": "", "forms": forms, "sort": "", "see": "",
                            "see_also": ""})
    if not entries:
        problems.append("No terms were found in the file.")
    return entries, problems


def write_term_csv(path: str | Path, entries: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        for e in entries:
            wr.writerow([e.get("heading", ""), e.get("sub", ""), " | ".join(e.get("forms", [])),
                         e.get("sort", ""), e.get("see", ""), e.get("see_also", "")])


def sample_csv() -> str:
    return ("heading,subentry,match forms,sort as,see,see also\n"
            "λόγος,,λόγος | λόγου | λόγῳ | λόγον | λόγοι | λόγων | λόγοις | λόγους,,,\n"
            "חֶסֶד,,חֶסֶד | חַסְדּוֹ | חֲסָדִים,,,\n"
            "covenant,,covenant | covenants,,,\n"
            "covenant,Davidic,Davidic covenant,,,\n"
            "covenant,new,new covenant,,,\n"
            "hesed,,,,חֶסֶד,\n"
            "justification,,justification | justified | justify,,,sanctification\n")
