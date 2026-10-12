"""Book catalog: sections, canonical orders, chapter counts, and the active
language's display names.  A `Catalog` is built from the user's settings
(language, Apocrypha on/off, custom books, section order, OT order) and is
what the parser, index writer and proof list consult.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Sections.  Placeholders are planned corpora that can't be enabled yet.
# ---------------------------------------------------------------------------
SECTION_KEYS = ["OT", "AP", "NT", "OTHER"]
PLACEHOLDER_SECTIONS = {
    "DSS": "Dead Sea Scrolls",
    "JOS": "Josephus",
    "PHILO": "Philo",
    "RAB": "Rabbinic literature",
    "PSEUD": "Pseudepigrapha",
    "APF": "Apostolic Fathers",
}
SECTION_LETTER = {"OT": "O", "AP": "A", "NT": "N", "OTHER": "X"}
DEFAULT_SECTION_ORDER = ["OT", "AP", "NT", "OTHER"]

# id, chapters  (chapters is a generous ceiling covering versification differences)
OT_BOOKS = [
    ("Gen", 50), ("Exod", 40), ("Lev", 27), ("Num", 36), ("Deut", 34), ("Josh", 24),
    ("Judg", 21), ("Ruth", 4), ("1Sam", 31), ("2Sam", 24), ("1Kgs", 22), ("2Kgs", 25),
    ("1Chr", 29), ("2Chr", 36), ("Ezra", 10), ("Neh", 13), ("Esth", 10), ("Job", 42),
    ("Ps", 150), ("Prov", 31), ("Eccl", 12), ("Song", 8), ("Isa", 66), ("Jer", 52),
    ("Lam", 5), ("Ezek", 48), ("Dan", 12), ("Hos", 14), ("Joel", 4), ("Amos", 9),
    ("Obad", 1), ("Jonah", 4), ("Mic", 7), ("Nah", 3), ("Hab", 3), ("Zeph", 3),
    ("Hag", 2), ("Zech", 14), ("Mal", 4),
]
AP_BOOKS = [
    ("Tob", 14), ("Jdt", 16), ("AddEsth", 16), ("Wis", 19), ("Sir", 51), ("Bar", 6),
    ("EpJer", 1), ("AddDan", 14), ("PrAzar", 1), ("Sus", 1), ("Bel", 1), ("1Macc", 16),
    ("2Macc", 15), ("3Macc", 7), ("4Macc", 18), ("1Esd", 9), ("2Esd", 16), ("PrMan", 1),
    ("Ps151", 1),
]
NT_BOOKS = [
    ("Matt", 28), ("Mark", 16), ("Luke", 24), ("John", 21), ("Acts", 28), ("Rom", 16),
    ("1Cor", 16), ("2Cor", 13), ("Gal", 6), ("Eph", 6), ("Phil", 4), ("Col", 4),
    ("1Thess", 5), ("2Thess", 3), ("1Tim", 6), ("2Tim", 4), ("Titus", 3), ("Phlm", 1),
    ("Heb", 13), ("Jas", 5), ("1Pet", 5), ("2Pet", 3), ("1John", 5), ("2John", 1),
    ("3John", 1), ("Jude", 1), ("Rev", 22),
]

OT_ORDERS = {
    "christian": [b for b, _ in OT_BOOKS],
    # Tanakh as printed in JPS and Koren editions
    "tanakh_jps": ["Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "1Sam", "2Sam", "1Kgs",
                   "2Kgs", "Isa", "Jer", "Ezek", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic",
                   "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal", "Ps", "Prov", "Job", "Song",
                   "Ruth", "Lam", "Eccl", "Esth", "Dan", "Ezra", "Neh", "1Chr", "2Chr"],
    # Tanakh as in BHS (Leningrad Codex Ketuvim order, Chronicles last)
    "tanakh_bhs": ["Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "1Sam", "2Sam", "1Kgs",
                   "2Kgs", "Isa", "Jer", "Ezek", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic",
                   "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal", "Ps", "Job", "Prov", "Ruth",
                   "Song", "Eccl", "Lam", "Esth", "Dan", "Ezra", "Neh", "1Chr", "2Chr"],
}
OT_ORDER_LABELS = {
    "christian": "English Bible order",
    "tanakh_jps": "Tanakh order (JPS / Koren)",
    "tanakh_bhs": "Tanakh order (BHS / Leningrad)",
}

BUILTIN: dict[str, tuple[str, int]] = {}
for _sec, _lst in (("OT", OT_BOOKS), ("AP", AP_BOOKS), ("NT", NT_BOOKS)):
    for _id, _ch in _lst:
        BUILTIN[_id] = (_sec, _ch)


@dataclass
class BookInfo:
    id: str
    section: str
    chapters: int
    name: str                      # display name in the active language
    rank: int = 0                  # position within its section
    custom: bool = False

    @property
    def single_chapter(self) -> bool:
        return self.chapters == 1


@dataclass
class Catalog:
    books: dict = field(default_factory=dict)       # id -> BookInfo
    section_order: list = field(default_factory=lambda: list(DEFAULT_SECTION_ORDER))
    split: str = "single"                            # single | testaments | sections
    section_titles: dict = field(default_factory=dict)
    index_title: str = "Scripture Index"
    label_sep: str = ":"
    numerals: str = "arabic"                         # arabic | hebrew
    ap_indexed: bool = False                         # the Apocrypha is always recognized; indexed if True
    verses: dict = field(default_factory=dict)       # id -> (English counts, original-text counts)

    def verse_max(self, book_id: str, chapter: int, numbering: str = "any") -> int | None:
        """Highest verse of a chapter (English, original, or either), or None if unknown."""
        v = self.verses.get(book_id)
        if not v:
            return None
        eng, orig = v
        e = eng[chapter - 1] if 0 < chapter <= len(eng) else 0
        o = orig[chapter - 1] if 0 < chapter <= len(orig) else 0
        return {"eng": e, "orig": o}.get(numbering, max(e, o))

    def chapter_max(self, book_id: str) -> int:
        v = self.verses.get(book_id)
        if v:
            return max(len(v[0]), len(v[1]))
        return self.books[book_id].chapters

    def get(self, book_id: str) -> BookInfo:
        return self.books[book_id]

    def name(self, book_id: str) -> str:
        b = self.books.get(book_id)
        return b.name if b else book_id

    def section_rank(self, section: str) -> int:
        try:
            return self.section_order.index(section) + 1
        except ValueError:
            return 9

    def book_key(self, book_id: str) -> str:
        b = self.books[book_id]
        return f"{self.section_rank(b.section)}{b.rank:03d}"

    def index_group(self, book_id: str) -> str | None:
        """Which INDEX field (\\f letter) an entry belongs to, or None for one index."""
        if self.split == "single":
            return None
        sec = self.books[book_id].section
        if self.split == "testaments":
            # the Apocrypha is grouped with the Old Testament
            return {"NT": "N", "OTHER": "X"}.get(sec, "O")
        return SECTION_LETTER.get(sec, "X")

    def groups_in_order(self) -> list[tuple[str, str]]:
        """[(letter, title)] for the INDEX fields to insert, in section order."""
        if self.split == "single":
            return []
        if self.split == "testaments":
            out = []
            for sec in self.section_order:
                if sec in ("OT", "NT", "OTHER"):
                    out.append((SECTION_LETTER[sec], self.section_titles.get(sec, sec)))
            return out
        return [(SECTION_LETTER[s], self.section_titles.get(s, s)) for s in self.section_order
                if s in SECTION_LETTER]

    def by_name(self) -> dict:
        return {b.name: b for b in self.books.values()}


def build_catalog(profile: dict, settings: dict) -> Catalog:
    """Assemble the catalog for one language profile and the user's settings."""
    lang = profile["code"]
    lset = settings.get("languages", {}).get(lang, {})
    ot_order = settings.get("ot_order") or profile.get("default_ot_order", "christian")
    order = OT_ORDERS.get(ot_order, OT_ORDERS["christian"])
    cat = Catalog()
    cat.section_order = [s for s in settings.get("section_order", DEFAULT_SECTION_ORDER)
                         if s in SECTION_KEYS] or list(DEFAULT_SECTION_ORDER)
    for s in SECTION_KEYS:
        if s not in cat.section_order:
            cat.section_order.append(s)
    cat.split = settings.get("index_layout", "single")
    titles = dict(profile.get("section_titles", {}))
    titles.update(lset.get("section_titles", {}))
    cat.section_titles = titles
    cat.index_title = lset.get("index_title") or profile.get("index_title", "Scripture Index")
    cat.label_sep = profile.get("label_sep", ":")
    cat.numerals = profile.get("numerals", "arabic")

    names = profile.get("names", {})
    name_over = lset.get("names", {})
    cat.ap_indexed = bool(settings.get("apocrypha", False))
    data = verse_data()
    for sec, lst in (("OT", OT_BOOKS), ("AP", AP_BOOKS), ("NT", NT_BOOKS)):
        for i, (bid, ch) in enumerate(lst):
            rank = order.index(bid) + 1 if sec == "OT" else i + 1
            nm = name_over.get(bid) or names.get(bid) or ENGLISH_FALLBACK.get(bid, bid)
            cat.books[bid] = BookInfo(bid, sec, ch, nm, rank)
            if bid in data["eng"] or bid in data["orig"]:
                cat.verses[bid] = (data["eng"].get(bid, []), data["orig"].get(bid, []))
    for cb in settings.get("custom_books", []):
        bid = cb.get("id") or ("X_" + cb.get("name", "?"))
        sec = cb.get("section", "OTHER")
        if sec not in SECTION_KEYS:
            sec = "OTHER"
        cat.books[bid] = BookInfo(bid, sec, int(cb.get("chapters") or 150), cb.get("name", bid),
                                  int(cb.get("position") or 500), True)
    return cat


_VERSES = None


def data_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "indicat" / "data"
    return p if p.exists() else Path(__file__).resolve().parent / "data"


def verse_data() -> dict:
    """Highest verse of each chapter (tools/build_data.py): {"eng": {...}, "orig": {...}}."""
    global _VERSES
    if _VERSES is None:
        try:
            _VERSES = json.loads((data_dir() / "verses.json").read_text(encoding="utf-8"))
        except Exception:
            _VERSES = {"eng": {}, "orig": {}}
    return _VERSES


ENGLISH_FALLBACK = {
    "Gen": "Genesis", "Exod": "Exodus", "Lev": "Leviticus", "Num": "Numbers", "Deut": "Deuteronomy",
    "Josh": "Joshua", "Judg": "Judges", "Ruth": "Ruth", "1Sam": "1 Samuel", "2Sam": "2 Samuel",
    "1Kgs": "1 Kings", "2Kgs": "2 Kings", "1Chr": "1 Chronicles", "2Chr": "2 Chronicles",
    "Ezra": "Ezra", "Neh": "Nehemiah", "Esth": "Esther", "Job": "Job", "Ps": "Psalms",
    "Prov": "Proverbs", "Eccl": "Ecclesiastes", "Song": "Song of Solomon", "Isa": "Isaiah",
    "Jer": "Jeremiah", "Lam": "Lamentations", "Ezek": "Ezekiel", "Dan": "Daniel", "Hos": "Hosea",
    "Joel": "Joel", "Amos": "Amos", "Obad": "Obadiah", "Jonah": "Jonah", "Mic": "Micah",
    "Nah": "Nahum", "Hab": "Habakkuk", "Zeph": "Zephaniah", "Hag": "Haggai", "Zech": "Zechariah",
    "Mal": "Malachi", "Tob": "Tobit", "Jdt": "Judith", "AddEsth": "Additions to Esther",
    "Wis": "Wisdom of Solomon", "Sir": "Sirach", "Bar": "Baruch", "EpJer": "Letter of Jeremiah",
    "AddDan": "Additions to Daniel", "PrAzar": "Prayer of Azariah", "Sus": "Susanna",
    "Bel": "Bel and the Dragon", "1Macc": "1 Maccabees", "2Macc": "2 Maccabees",
    "3Macc": "3 Maccabees", "4Macc": "4 Maccabees", "1Esd": "1 Esdras", "2Esd": "2 Esdras",
    "PrMan": "Prayer of Manasseh", "Ps151": "Psalm 151", "Matt": "Matthew", "Mark": "Mark",
    "Luke": "Luke", "John": "John", "Acts": "Acts", "Rom": "Romans", "1Cor": "1 Corinthians",
    "2Cor": "2 Corinthians", "Gal": "Galatians", "Eph": "Ephesians", "Phil": "Philippians",
    "Col": "Colossians", "1Thess": "1 Thessalonians", "2Thess": "2 Thessalonians",
    "1Tim": "1 Timothy", "2Tim": "2 Timothy", "Titus": "Titus", "Phlm": "Philemon",
    "Heb": "Hebrews", "Jas": "James", "1Pet": "1 Peter", "2Pet": "2 Peter", "1John": "1 John",
    "2John": "2 John", "3John": "3 John", "Jude": "Jude", "Rev": "Revelation",
}
